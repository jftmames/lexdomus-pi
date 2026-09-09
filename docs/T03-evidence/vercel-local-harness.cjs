const fs = require('node:fs');
const path = require('node:path');

// Diagnostic sandbox: no deployment, project link, credentials, or user cases.
const allowed = new Set([
  'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL',
  'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY',
  'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy',
]);
for (const name of Object.keys(process.env)) {
  if (!allowed.has(name)) delete process.env[name];
}
Object.assign(process.env, {
  CI: '1', USE_LLM: '0', NEXT_TELEMETRY_DISABLED: '1',
  VERCEL: '1', VERCEL_ENV: 'preview',
});

async function main() {
  const { glob } = require('@vercel/build-utils');
  const { build } = require('@vercel/next');
  const source = path.join(__dirname, 'source');
  const workPath = path.join(__dirname, 'build');
  const vercel = JSON.parse(fs.readFileSync(path.join(source, 'vercel.json'), 'utf8'));
  const files = await glob('**', source);
  console.log(JSON.stringify({
    diagnostic: 'local builder only, no hosted project settings',
    sourceCommit: '86e14b53145ca0ba0c4bbdd450a6e0e6b08f4194',
    builder: require('@vercel/next/package.json').version,
    utils: require('@vercel/build-utils/package.json').version,
    node: process.version,
    fileCount: Object.keys(files).length,
  }));
  const result = await build({
    files, entrypoint: vercel.builds[0].src, workPath, repoRootPath: workPath,
    config: vercel.builds[0].config, meta: {},
  });
  console.log(JSON.stringify({
    result: 'success', outputCount: Object.keys(result.output || {}).length,
    routes: result.routes?.length, outputVersion: result.buildOutputVersion,
    outputPath: result.buildOutputPath,
  }));
}
main().catch(error => {
  console.error(error.stack || String(error));
  if (error.code) console.error('ERROR_CODE=' + error.code);
  process.exitCode = 1;
});
