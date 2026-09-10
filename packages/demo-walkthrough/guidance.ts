export const guidanceCss = `
*{scrollbar-width:none!important}*::-webkit-scrollbar{display:none!important}
[data-player-focus]{outline:3px solid #b9ed72!important;outline-offset:8px!important;border-radius:5px!important;box-shadow:0 0 0 10px #b9ed7230,0 0 0 100vmax rgba(0,0,0,.5)!important;scroll-margin-top:40px!important}`;
export function markTarget(target: HTMLElement) {
  target.setAttribute("data-player-focus", "true");
}
