/**
 * Custom webpack configuration for rsp-jupyter-extensions
 *
 * This configuration suppresses warnings from sql-formatter's missing source maps
 * and invalid dependency paths, which are harmless but clutter the build output.
 *
 * The sql-formatter package references source TypeScript files in its source maps
 * that aren't included in the npm package, causing webpack to emit warnings.
 */

module.exports = {
  ignoreWarnings: [
    // Ignore warnings about invalid dependencies from sql-formatter
    warning => {
      return (
        warning.module &&
        warning.module.resource &&
        warning.module.resource.includes('node_modules/sql-formatter')
      );
    }
  ]
};
