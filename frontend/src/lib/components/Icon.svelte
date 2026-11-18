<script lang="ts">
  import { icons, type IconName } from '../icons';

  interface Props {
    name?: IconName;
    /** eigener Pfad statt eines benannten Icons */
    d?: string;
    size?: number;
    strokeWidth?: number;
    color?: string;
  }

  let { name, d, size = 18, strokeWidth = 1.8, color = 'currentColor' }: Props = $props();
  const path = $derived(d ?? (name ? icons[name] : ''));
</script>

<svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width={strokeWidth} stroke-linecap="round" stroke-linejoin="round">
  <path d={path}></path>
</svg>
