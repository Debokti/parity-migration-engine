// Federated-module manifest for the Northstar Drawdown MFE.
//
// Wiring note: production federation pairs this manifest with the
// @angular-architects/module-federation builder (webpack.config.js merging
// this plugin list). Until that build runs, the legacy popup
// (mfe-popup.jspf) mounts the module through its iframe fallback to
// http://localhost:4200/, and script injection uses
// window.mountNorthstarDrawdownMfe from src/app/drawdown/mfe-mount.ts.
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  output: {
    uniqueName: 'northstarDrawdown',
    publicPath: 'auto'
  },
  optimization: { runtimeChunk: false },
  plugins: [
    new ModuleFederationPlugin({
      name: 'northstarDrawdown',
      filename: 'remoteEntry.js',
      exposes: {
        './DrawdownComponent': './src/app/drawdown/drawdown.component.ts',
        './MfeMount': './src/app/drawdown/mfe-mount.ts'
      },
      shared: {
        '@angular/core': { singleton: true, strictVersion: false, requiredVersion: '^17.3.0' },
        '@angular/common': { singleton: true, strictVersion: false, requiredVersion: '^17.3.0' },
        '@angular/platform-browser': { singleton: true, strictVersion: false, requiredVersion: '^17.3.0' },
        '@angular/forms': { singleton: true, strictVersion: false, requiredVersion: '^17.3.0' },
        rxjs: { singleton: true, strictVersion: false, requiredVersion: '~7.8.0' }
      }
    })
  ]
};
