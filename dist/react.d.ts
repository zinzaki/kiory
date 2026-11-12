import type { SVGProps, ReactElement } from 'react';
import type { KioryName } from './kiory.js';
export interface KioryIconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> { name: KioryName; size?: number | string; title?: string }
export declare function KioryIcon(props: KioryIconProps): ReactElement;
export default KioryIcon;
