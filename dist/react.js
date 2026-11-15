// <KioryIcon name="search" size={20} />: takes the text colour
import { createElement } from 'react';
import { icons } from './kiory.js';
export function KioryIcon({ name, size = 24, title, ...rest }) {
  if (!Object.hasOwn(icons, name)) throw new Error(`Kiory: no icon named "${name}"`);
  const label = title ? String(title).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])) : '';
  const body = (label ? `<title>${label}</title>` : '') + icons[name];
  return createElement('svg', { xmlns: 'http://www.w3.org/2000/svg', width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    role: title ? 'img' : undefined, 'aria-hidden': title ? undefined : true, ...rest, dangerouslySetInnerHTML: { __html: body } });
}
export default KioryIcon;
