// Module-federation mount hook for the Northstar Drawdown MFE.
//
// Standalone: index.html already contains <app-drawdown>, so main.ts takes the
// bootstrapStandalone() path. Federated: the legacy popup (mfe-popup.jspf)
// injects remoteEntry.js and either upgrades the <northstar-drawdown-mfe>
// custom element already in the host container or calls
// window.mountNorthstarDrawdownMfe(host) explicitly. Until the federated
// build runs, the popup falls back to an iframe pointed at :4200.
import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { DrawdownComponent } from './drawdown.component';

export const MFE_ELEMENT_NAME = 'northstar-drawdown-mfe';

let bootstrapped = false;

function appProviders() {
  return [provideHttpClient(withFetch())];
}

async function bootstrapInto(host: Element): Promise<void> {
  if (bootstrapped) return;
  bootstrapped = true;
  const root = document.createElement('app-drawdown');
  host.appendChild(root);
  await bootstrapApplication(DrawdownComponent, { providers: appProviders() });
}

export function mountNorthstarDrawdownMfe(host: Element | string): Promise<void> {
  const el = typeof host === 'string' ? document.querySelector(host) : host;
  if (!el) return Promise.reject(new Error('mount target not found'));
  return bootstrapInto(el);
}

export function registerDrawdownMfe(): void {
  const w = window as unknown as { mountNorthstarDrawdownMfe?: typeof mountNorthstarDrawdownMfe };
  if (!w.mountNorthstarDrawdownMfe) w.mountNorthstarDrawdownMfe = mountNorthstarDrawdownMfe;
  if (!customElements.get(MFE_ELEMENT_NAME)) {
    customElements.define(
      MFE_ELEMENT_NAME,
      class extends HTMLElement {
        connectedCallback(): void {
          void bootstrapInto(this);
        }
      }
    );
  }
}

export function bootstrapStandalone(): void {
  if (bootstrapped) return;
  const root = document.querySelector('app-drawdown');
  if (!root || root.hasAttribute('ng-version')) return;
  bootstrapped = true;
  void bootstrapApplication(DrawdownComponent, { providers: appProviders() }).catch((err) =>
    console.error(err)
  );
}
