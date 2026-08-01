import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const trackedAndUntracked = execFileSync(
  'git',
  ['ls-files', '--cached', '--others', '--exclude-standard'],
  { encoding: 'utf8' },
)
  .split(/\r?\n/)
  .filter(Boolean);

const forbiddenNames = /(^|\/)(\.env|\.dev\.vars)(\.|$)/;
const allowedExamples = /\.example$/;
const patterns = [
  { label: 'DeepSeek/OpenAI-style key', expression: /sk-[a-zA-Z0-9_-]{20,}/ },
  { label: 'GitHub token', expression: /gh[pousr]_[a-zA-Z0-9]{30,}/ },
  {
    label: 'assigned API secret',
    expression:
      /(DEEPSEEK_API_KEY|CLOUDFLARE_API_TOKEN|IP_HASH_SECRET)\s*=\s*(?!replace_|generate_|your_|test-)[^\s#]{16,}/i,
  },
];

const findings = [];
for (const file of trackedAndUntracked) {
  const normalized = file.replaceAll('\\', '/');
  if (normalized === 'scripts/scan-secrets.mjs') continue;
  if (forbiddenNames.test(normalized) && !allowedExamples.test(normalized)) {
    findings.push(`${normalized}: environment/secret file must not be tracked`);
    continue;
  }

  let content;
  try {
    content = readFileSync(file, 'utf8');
  } catch {
    continue;
  }
  if (content.includes('\u0000')) continue;
  for (const pattern of patterns) {
    if (pattern.expression.test(content)) findings.push(`${normalized}: ${pattern.label}`);
  }
}

if (findings.length) {
  console.error('Potential secrets detected:');
  findings.forEach((finding) => console.error(`- ${finding}`));
  process.exit(1);
}

console.log(`Secret scan passed (${trackedAndUntracked.length} project files checked).`);
