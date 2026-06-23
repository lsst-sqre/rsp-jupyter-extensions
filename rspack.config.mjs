import { defineConfig } from '@rspack/cli';

export default defineConfig({
  entry: {
    main: './src/index.ts'
  },
  ignoreWarnings: [{ module: /sql-formatter/ }]
});
