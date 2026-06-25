// Custom build config merged into @jupyter/builder's internal rspack config.
//
// jupyter-builder does NOT auto-discover this file. It is loaded only because
// package.json -> jupyterlab.webpackConfig points at it, after which the
// builder does roughly:
//
//   merge(baseConfig, { mode, output, plugins, ... }, <this object>, { module: { rules } })
//
// So this module must (a) be CommonJS, because the builder loads it with
// require(), and (b) export a plain config fragment (NOT @rspack/cli's
// defineConfig wrapper) that webpack-merge can fold into the array.
//
// Purpose: silence the "Failed to parse source map" warnings that
// source-map-loader emits for sql-formatter in development builds. The
// published sql-formatter package ships source maps that reference its
// original .ts sources, which are not included in the npm tarball, so the
// loader cannot resolve them. The warnings are harmless.
module.exports = {
  ignoreWarnings: [{ module: /sql-formatter/ }]
};
