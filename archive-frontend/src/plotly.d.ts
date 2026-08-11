declare module 'plotly.js-dist-min' {
  import type { Data, Layout, Config } from 'plotly.js'
  const Plotly: { react: (element: HTMLElement, data: Data[], layout?: Partial<Layout>, config?: Partial<Config>) => Promise<void> }
  export default Plotly
}