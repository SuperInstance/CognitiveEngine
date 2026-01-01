import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    'index': './src/index.ts'
  },
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'es2022',
  minify: process.env.NODE_ENV === 'production',
  splitting: false,
  shims: true,
});
