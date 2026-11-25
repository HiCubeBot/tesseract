#!/usr/bin/env node
/**
 * Werkzeug für die Mehrsprachigkeit (siehe src/lib/i18n.ts).
 *
 *   node scripts/i18n.mjs check       feste Texte ohne t() und fehlende Übersetzungen melden
 *   node scripts/i18n.mjs keys        alle Schlüssel (deutsche Texte) als JSON ausgeben
 *   node scripts/i18n.mjs transform   feste Texte in t('…') einpacken (einmalig/bei Bedarf)
 *   node scripts/i18n.mjs candidates  wie transform, aber nur anzeigen
 *
 * Schlüssel ist der deutsche Text selbst; Platzhalter {0}, {1} … stehen für eingesetzte Werte.
 * `check` läuft in `npm run check` mit – neue feste Texte fallen so sofort auf.
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import ts from 'typescript';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'src');
const EN = join(SRC, 'lib', 'i18n', 'en.json');

// Prototyp-Screens aus dem Design und die i18n selbst bleiben außen vor
const SKIP_DIRS = new Set(['screens']);
const SKIP_FILES = new Set(['ScreenIndex.svelte', 'routes.ts', 'main.ts', 'vite-env.d.ts', 'icons.ts', 'i18n.ts']);

function files(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (!SKIP_DIRS.has(name) && name !== 'i18n') out.push(...files(p));
    } else if ((name.endsWith('.svelte') || name.endsWith('.ts')) && !SKIP_FILES.has(name)) out.push(p);
  }
  return out;
}

// ---------- Was ist ein Text für Menschen? ----------

const WORD = /[A-Za-zÄÖÜäöüß]{2,}/;
const UMLAUT = /[ÄÖÜäöüß]/;

/** Text in Markup: alles mit einem Wort aus Buchstaben */
function isMarkupText(s) {
  const v = s.trim();
  if (!v || !WORD.test(v)) return false;
  // reine Technik ohne Satz: Pfade, Header, Befehle in <code>
  if (/^[/.#@~$*-]/.test(v) && !/\s/.test(v)) return false;
  if (/^[a-z]+:\/\//.test(v) && !/\s/.test(v)) return false;
  if (/^-{3,}/.test(v)) return false; // PEM-Platzhalter
  if (/^[\w-]*\{\d\}[\w{}-]*$/.test(v) && !/^[A-ZÄÖÜ]/.test(v)) return false;
  if (!/\s/.test(v) && (/^[\w.*+-]+@[\w.-]+$/.test(v) || /^[\w*-]+(\.[\w-]+)+$/.test(v) || /=/.test(v))) return false;
  return true;
}

const LABEL_KEYS = new Set([
  'label', 'title', 'text', 'note', 'description', 'hint', 'sub', 'detail', 'message', 'subtitle',
  'placeholder', 'help', 'heading', 'empty', 'tip', 'caption', 'name', 'short', 'long', 'what', 'why', 'action', 'unit'
]);

/** Zeichenkette im Code: Satz, Beschriftung oder Wort mit Umlaut – keine Bezeichner */
function isCodeText(s, ctx) {
  const v = s.trim();
  if (!v || !WORD.test(v)) return false;
  if (/^[/.#@~$&?=-]/.test(v)) return false; // Pfade, Selektoren, Query, PEM
  if (/^(https?:|mailto:|data:|var\(|rgba?\(|#[0-9a-f]{3})/i.test(v)) return false;
  if (/^[MmLlHhVvCcSsQqTtAaZz0-9 .,-]+$/.test(v) && /\d/.test(v)) return false; // SVG-Pfade
  if (/[{}<>;=]|=>|\(\)/.test(v) && !/[.!?…]$/.test(v)) return false; // Code
  if (/^[a-z]+(-[a-z]+)+$/.test(v)) return false; // css-klassen, kebab-case
  if (/^[a-z][a-zA-Z0-9]*$/.test(v) && !UMLAUT.test(v) && !ctx.labelish) return false; // camelCase/Bezeichner
  if (/^[A-Z0-9_]+$/.test(v) && v.length > 1 && !ctx.labelish) return false; // KONSTANTEN, Abkürzungen
  if (/^\w+\/\w+/.test(v) && !/\s/.test(v)) return false; // MIME, Pfade ohne Leerzeichen
  if (!/\s/.test(v) && (/^[\w.*+-]+@[\w.-]+$/.test(v) || /^[\w*-]+(\.[\w-]+)+$/.test(v))) return false; // E-Mail, Domain
  if (/=/.test(v) && !/\s\w+\s/.test(v)) return false; // KEY=wert, LDAP-DN
  if (/^[\w-]*\{\d\}[\w{}-]*$/.test(v) && !/^[A-ZÄÖÜ]/.test(v)) return false; // drift-{0}, token-{0}
  if (/\s/.test(v)) return true;
  if (UMLAUT.test(v)) return true;
  // einzelnes Wort: nur in beschriftendem Zusammenhang; kleingeschrieben nur bei label & Co.
  if (/^[a-z]/.test(v)) return !!ctx.strongLabel;
  return ctx.labelish && /[a-zäöü]/.test(v);
}

// ---------- TypeScript: Zeichenketten finden ----------

const EQ = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken
]);
const SKIP_CALLS = /^(api\.(get|post|put|del)|fetch|fetchRetry|t|tn|document\.\w+|window\.\w+|localStorage\.\w+|sessionStorage\.\w+|console\.\w+|new URL|new Intl\.\w+|\w+\.(querySelector|querySelectorAll|getItem|setItem|removeItem|addEventListener|removeEventListener|toLocaleString|toLocaleDateString|toLocaleTimeString|startsWith|endsWith|includes|split|replace|replaceAll|match|test|indexOf|padStart|padEnd|join|setAttribute|getAttribute|has|get|delete|search|append|set)|router\.go|new RegExp|RegExp|structuredClone|encodeURIComponent|decodeURIComponent)$/;

function callName(call, sf) {
  return call.expression.getText(sf).replace(/\s+/g, '');
}

/** Liefert Bereiche [start, end, replacement] für Zeichenketten in einem TS-Quelltext */
function scriptEdits(code, { fileName = 'x.ts', offset = 0 } = {}) {
  const sf = ts.createSourceFile(fileName, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const edits = [];

  function context(node) {
    const p = node.parent;
    if (!p) return null;
    if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p) || ts.isExternalModuleReference(p)) return null;
    if (ts.isLiteralTypeNode(p)) return null;
    if (ts.isPropertyAssignment(p) && p.name === node) return null;
    if (ts.isPropertySignature(p) || ts.isEnumMember(p)) return null;
    if (ts.isElementAccessExpression(p) && p.argumentExpression === node) return null;
    if (ts.isBinaryExpression(p) && EQ.has(p.operatorToken.kind)) return null;
    if (ts.isCaseClause(p)) return null;
    if (ts.isComputedPropertyName(p)) return null;
    if ((ts.isCallExpression(p) || ts.isNewExpression(p)) && p.arguments?.includes(node)) {
      const name = callName(p, sf);
      if (SKIP_CALLS.test(name) || /^new (URL|RegExp|Intl)/.test(`new ${name}`) && ts.isNewExpression(p)) return null;
      if (/^(toasts\.show|confirm|alert|prompt|new Error|Error|new ApiError)$/.test(ts.isNewExpression(p) ? `new ${name}` : name))
        return { labelish: true };
      // toasts.show(tone, text): Ton ist ein Bezeichner
      return { labelish: false };
    }
    if (ts.isPropertyAssignment(p)) {
      const key = p.name.getText(sf).replace(/['"]/g, '');
      // Wert in einer Beschriftungs-Tabelle (Record<…, string>) oder label-artiger Schlüssel
      const obj = p.parent;
      const inTable = ts.isObjectLiteralExpression(obj) && obj.properties.every((q) => ts.isPropertyAssignment(q) && (ts.isStringLiteral(q.initializer) || ts.isNoSubstitutionTemplateLiteral(q.initializer) || ts.isTemplateExpression(q.initializer)));
      if (/^(tone|kind|id|key|icon|href|path|type|variant|size|color|value|mode|source|status|unit_id|d|field|sort|format)$/i.test(key) && !inTable) return null;
      if (/^(day|month|year|hour|minute|second|weekday|era|style|notation|unitDisplay|timeZone|timeZoneName|currency|compactDisplay|hourCycle|numberingSystem|calendar|localeMatcher)$/.test(key)) return null;
      return { labelish: LABEL_KEYS.has(key) || inTable, strongLabel: LABEL_KEYS.has(key) };
    }
    if (ts.isConditionalExpression(p) || ts.isReturnStatement(p) || ts.isArrayLiteralExpression(p) || ts.isBinaryExpression(p) || ts.isParenthesizedExpression(p) || ts.isVariableDeclaration(p) || ts.isArrowFunction(p) || ts.isTemplateSpan(p) || ts.isBinaryExpression(p))
      return { labelish: ts.isConditionalExpression(p) || ts.isReturnStatement(p) || ts.isArrowFunction(p) };
    return { labelish: false };
  }

  function visit(node) {
    if (ts.isCallExpression(node) && /^(t|tn)$/.test(node.expression.getText(sf))) return; // schon übersetzt
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      const ctx = context(node);
      if (ctx && isCodeText(node.text, ctx)) {
        edits.push([offset + node.getStart(sf), offset + node.getEnd(), `t(${JSON.stringify(node.text).replace(/^"|"$/g, "'").replace(/\\"/g, '"').replace(/(?<!\\)'/g, (m, i, all) => (i === 0 || i === all.length - 1 ? m : "\\'"))})`, node.text]);
        return;
      }
    } else if (ts.isTemplateExpression(node)) {
      const ctx = context(node);
      const parts = [node.head.text, ...node.templateSpans.map((s) => s.literal.text)];
      const joined = parts.join(' ');
      if (ctx && isCodeText(joined.replace(/\s+/g, ' '), { labelish: true }) && /[A-Za-zÄÖÜäöüß]{3,}/.test(parts.join(''))) {
        let key = node.head.text;
        const args = [];
        node.templateSpans.forEach((s, i) => {
          key += `{${i}}` + s.literal.text;
          args.push(s.expression.getText(sf));
        });
        // innere Zeichenketten der Ausdrücke ebenfalls prüfen
        const inner = args.map((a, i) => {
          const sub = scriptEdits(a, { fileName });
          return applyEdits(a, sub);
        });
        edits.push([offset + node.getStart(sf), offset + node.getEnd(), `t(${quote(key)}, ${inner.join(', ')})`, key]);
        return;
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return edits;
}

function quote(s) {
  return "'" + s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n') + "'";
}

function applyEdits(code, edits, base = 0) {
  const sorted = [...edits].sort((a, b) => b[0] - a[0]);
  let out = code;
  for (const [s, e, r] of sorted) out = out.slice(0, s - base) + r + out.slice(e - base);
  return out;
}

// ---------- Svelte ----------

const ATTR_ALWAYS = new Set([
  'placeholder', 'title', 'aria-label', 'alt', 'label', 'description', 'subtitle', 'text', 'primaryLabel',
  'secondaryLabel', 'actionLabel', 'confirmLabel', 'cancelLabel', 'groupLabel', 'hint', 'sub', 'empty',
  'heading', 'message', 'note', 'caption', 'emptyText', 'loadingLabel', 'legend', 'help', 'aria-description',
  'tooltip', 'confirmText', 'detail', 'unit'
]);
const ATTR_NEVER = /^(class|style|id|href|type|name|for|role|value|pattern|d|src|rel|target|accept|autocomplete|inputmode|lang|method|action|viewBox|points|transform|fill|stroke|tone|variant|size|icon|key|tab|active|current|data-.*|aria-(labelledby|describedby|controls|current|hidden|live|expanded|selected|checked|pressed|haspopup|modal|busy)|width|height|min|max|step|maxlength|minlength|spellcheck|download|xmlns|stroke-.*|fill-.*|cx|cy|r|x|y|x1|x2|y1|y2|rx|ry|dx|dy|offset|stop-color|font-.*|text-anchor|dominant-baseline|path|mode|kind|color|sparkColor|series|format)$/;

function svelteEdits(src, file) {
  const ast = parse(src, { modern: true, filename: file });
  const edits = [];

  // Ausdrücke im Markup ({…}, Attribut-Ausdrücke)
  function exprEdits(node) {
    const code = src.slice(node.start, node.end);
    for (const e of scriptEdits(code, { offset: node.start })) edits.push(e);
  }

  function walkFragment(fragment) {
    const nodes = fragment?.nodes ?? [];
    // Läufe aus Text und {Ausdruck} zwischen Elementen
    let run = [];
    const flush = () => {
      if (run.length) handleRun(run);
      run = [];
    };
    for (const n of nodes) {
      if (n.type === 'Text' || n.type === 'ExpressionTag') run.push(n);
      else {
        flush();
        walkNode(n);
      }
    }
    flush();
  }

  function handleRun(run) {
    const texts = run.filter((n) => n.type === 'Text');
    if (!texts.some((n) => isMarkupText(n.data))) {
      run.filter((n) => n.type === 'ExpressionTag').forEach((n) => exprEdits(n.expression));
      return;
    }
    // führende/folgende Leerzeichen bleiben außerhalb
    const first = run[0];
    const last = run[run.length - 1];
    let start = first.start;
    let end = last.end;
    if (first.type === 'Text') start += first.raw.length - first.raw.trimStart().length;
    if (last.type === 'Text') end -= last.raw.length - last.raw.trimEnd().length;
    let key = '';
    const args = [];
    for (const n of run) {
      if (n.type === 'Text') key += n.data;
      else {
        const code = src.slice(n.expression.start, n.expression.end);
        const inner = applyEdits(code, scriptEdits(code));
        key += `{${args.length}}`;
        args.push(inner);
      }
    }
    key = key.replace(/\s+/g, ' ').trim();
    if (args.length === 1 && key === '{0}') return;
    const call = args.length ? `{t(${quote(key)}, ${args.join(', ')})}` : `{t(${quote(key)})}`;
    edits.push([start, end, call, key]);
  }

  function walkAttrs(node) {
    for (const a of node.attributes ?? []) {
      if (a.type === 'Attribute') {
        if (a.value === true) continue;
        const parts = Array.isArray(a.value) ? a.value : [a.value];
        const hasText = parts.some((p) => p.type === 'Text' && isMarkupText(p.data));
        const ok = ATTR_ALWAYS.has(a.name) || (!ATTR_NEVER.test(a.name) && !a.name.startsWith('on') && hasText && parts.some((p) => p.type === 'Text' && (/\s/.test(p.data.trim()) || UMLAUT.test(p.data)) && /^[A-ZÄÖÜ]/.test(p.data.trim())));
        if (hasText && ok) {
          let key = '';
          const args = [];
          for (const p of parts) {
            if (p.type === 'Text') key += p.data;
            else {
              const code = src.slice(p.expression.start, p.expression.end);
              key += `{${args.length}}`;
              args.push(applyEdits(code, scriptEdits(code)));
            }
          }
          const s = parts[0].start;
          const e = parts[parts.length - 1].end;
          // Anführungszeichen um den Wert mit ersetzen
          const qs = src[s - 1] === '"' || src[s - 1] === "'" ? s - 1 : s;
          const qe = src[e] === '"' || src[e] === "'" ? e + 1 : e;
          edits.push([qs, qe, `{t(${quote(key)}${args.length ? ', ' + args.join(', ') : ''})}`, key]);
        } else {
          for (const p of parts) if (p.type === 'ExpressionTag') exprEdits(p.expression);
        }
      } else if (a.type === 'ExpressionTag' || a.type === 'Attribute') {
        exprEdits(a.expression);
      } else if (a.expression && !['BindDirective', 'OnDirective', 'UseDirective', 'TransitionDirective', 'AnimateDirective', 'LetDirective', 'ClassDirective', 'StyleDirective'].includes(a.type)) {
        exprEdits(a.expression);
      } else if (a.type === 'SpreadAttribute' || a.type === 'AttachTag') {
        exprEdits(a.expression);
      }
    }
  }

  function walkNode(n) {
    switch (n.type) {
      case 'RegularElement':
      case 'Component':
      case 'SvelteElement':
      case 'SvelteComponent':
      case 'SvelteFragment':
      case 'SvelteSelf':
      case 'SlotElement':
      case 'TitleElement':
      case 'SvelteHead':
      case 'SvelteBoundary':
        if (n.name === 'style' || n.name === 'script' || n.name === 'code' || n.name === 'pre' || n.name === 'svg') {
          walkAttrs(n);
          if (n.name === 'code' || n.name === 'pre') return;
          return;
        }
        walkAttrs(n);
        walkFragment(n.fragment);
        break;
      case 'SvelteWindow':
      case 'SvelteDocument':
      case 'SvelteBody':
        break;
      case 'IfBlock':
        exprEdits(n.test);
        walkFragment(n.consequent);
        if (n.alternate) walkFragment(n.alternate);
        break;
      case 'EachBlock':
        exprEdits(n.expression);
        walkFragment(n.body);
        if (n.fallback) walkFragment(n.fallback);
        break;
      case 'AwaitBlock':
        exprEdits(n.expression);
        for (const k of ['pending', 'then', 'catch']) if (n[k]) walkFragment(n[k]);
        break;
      case 'KeyBlock':
        exprEdits(n.expression);
        walkFragment(n.fragment);
        break;
      case 'SnippetBlock':
        walkFragment(n.body);
        break;
      case 'RenderTag':
      case 'HtmlTag':
      case 'ConstTag':
        if (n.expression) exprEdits(n.expression);
        if (n.declaration) exprEdits(n.declaration);
        break;
      default:
        break;
    }
  }

  walkFragment(ast.fragment);
  for (const s of [ast.instance, ast.module]) {
    if (!s) continue;
    const start = s.content.start;
    const code = src.slice(start, s.content.end);
    edits.push(...scriptEdits(code, { offset: start }));
  }
  return { edits, ast };
}

function importPath(file) {
  let rel = relative(dirname(file), join(SRC, 'lib', 'i18n')).split(sep).join('/');
  if (!rel.startsWith('.')) rel = './' + rel;
  return rel;
}

function addImport(src, file, isSvelte) {
  if (/import \{[^}]*\bt\b[^}]*\} from '[^']*i18n'/.test(src)) return src;
  const line = `import { t } from '${importPath(file)}';`;
  if (!isSvelte) {
    const lines = src.split('\n');
    let i = 0;
    // nach Kopfkommentar und vorhandenen Imports
    let lastImport = -1;
    for (let j = 0; j < lines.length; j++) if (/^import /.test(lines[j])) lastImport = j;
    if (lastImport >= 0) {
      // mehrzeilige Imports: bis zur Zeile mit dem from
      let k = lastImport;
      while (k < lines.length && !/from ['"]/.test(lines[k]) && !/^import ['"]/.test(lines[k])) k++;
      lines.splice(k + 1, 0, line);
    } else {
      while (i < lines.length && (/^\s*(\/\/|\/\*|\*)/.test(lines[i]) || lines[i].trim() === '')) i++;
      lines.splice(i, 0, line);
    }
    return lines.join('\n');
  }
  const m = src.match(/<script(?![^>]*context="module")(?![^>]*\bmodule\b)[^>]*>\n/);
  if (m) return src.replace(m[0], `${m[0]}  ${line}\n`);
  return `<script lang="ts">\n  ${line}\n</script>\n\n` + src;
}

// ---------- Befehle ----------

function transformFile(file, write) {
  const src = readFileSync(file, 'utf8');
  const isSvelte = file.endsWith('.svelte');
  const edits = isSvelte ? svelteEdits(src, file).edits : scriptEdits(src, { fileName: file });
  // überlappende Bearbeitungen: die äußere gewinnt
  edits.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
  const kept = [];
  let lastEnd = -1;
  for (const e of edits) {
    if (e[0] >= lastEnd) {
      kept.push(e);
      lastEnd = e[1];
    }
  }
  if (!kept.length) return [];
  if (write) {
    let out = applyEdits(src, kept);
    out = addImport(out, file, isSvelte);
    writeFileSync(file, out);
  }
  return kept.map((e) => e[3]);
}

/** Alle Schlüssel aus t('…')-Aufrufen */
function collectKeys() {
  const keys = new Map();
  const re = /\bt\(\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g;
  for (const f of files(SRC)) {
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(re)) {
      const raw = m[1];
      // eslint-disable-next-line no-new-func
      const key = new Function(`return ${raw}`)();
      if (!keys.has(key)) keys.set(key, relative(SRC, f));
    }
  }
  return keys;
}

const cmd = process.argv[2] ?? 'check';
if (cmd === 'transform' || cmd === 'candidates') {
  let n = 0;
  for (const f of files(SRC)) {
    const keys = transformFile(f, cmd === 'transform');
    if (keys.length && cmd === 'candidates') {
      console.log(`\n== ${relative(SRC, f)}`);
      for (const k of keys) console.log('  ' + JSON.stringify(k));
    }
    n += keys.length;
  }
  console.error(`${n} Texte${cmd === 'transform' ? ' umgestellt' : ''}`);
} else if (cmd === 'keys') {
  console.log(JSON.stringify([...collectKeys().keys()], null, 1));
} else if (cmd === 'check') {
  let problems = 0;
  for (const f of files(SRC)) {
    const left = transformFile(f, false);
    for (const k of left) {
      console.log(`${relative(ROOT, f)}: fester Text ohne t(): ${JSON.stringify(k)}`);
      problems++;
    }
  }
  const en = JSON.parse(readFileSync(EN, 'utf8'));
  for (const [k, f] of collectKeys()) {
    if (!(k in en)) {
      console.log(`src/${f.split(sep).join('/')}: keine englische Übersetzung: ${JSON.stringify(k)}`);
      problems++;
    }
  }
  if (problems) {
    console.log(`\n${problems} Probleme – Texte in t('…') einpacken und in src/lib/i18n/en.json übersetzen.`);
    process.exit(1);
  }
  console.log('i18n: alles übersetzt');
} else {
  console.error('Befehl: check | keys | transform | candidates');
  process.exit(2);
}
