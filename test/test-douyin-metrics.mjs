import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, copyFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

// Run the actual fetch → argument conversion → SQLite pipeline with mocked HTTP
// adapters in an isolated workspace. Never read live cookies or write the live DB.
const root = mkdtempSync(join(tmpdir(), 'douyin-metrics-'));
const source = new URL('../crews/main/skills/published-track/scripts/', import.meta.url);
const scripts = join(root, 'skills/published-track/scripts');
const run = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
try {
  mkdirSync(scripts, { recursive: true });
  mkdirSync(join(root, 'skills/_shared'), { recursive: true });
  mkdirSync(join(root, 'logins'));
  writeFileSync(join(root, 'logins/douyin.json'), JSON.stringify({ cookies: [{ name: 'sessionid', value: 'test' }] }));
  for (const file of ['init-db.sh', 'update-metrics.sh', 'fetch-and-update-metrics.sh']) {
    copyFileSync(new URL(file, source), join(scripts, file));
  }
  writeFileSync(join(scripts, 'fetch-retro-data.ts'), readFileSync(new URL('fetch-retro-data.ts', source), 'utf8')
    .replace('join(homedir(), ".openclaw", "logins")', JSON.stringify(join(root, 'logins'))));
  writeFileSync(join(scripts, 'check-login.ts'), 'console.log(JSON.stringify({ok:true}))');
  writeFileSync(join(root, 'skills/_shared/douyin-web.ts'), `
import {readFileSync} from 'node:fs';
const fixture = JSON.parse(readFileSync(${JSON.stringify(join(root, 'fixture.json'))}, 'utf8'));
export async function douyinWebGet() { return {status:200,data:{aweme_detail:{statistics:fixture.public}}}; }
export async function douyinCreatorItem() { return fixture.creator === null ? null : {metrics:fixture.creator}; }
`);
  run('bash', [join(scripts, 'init-db.sh')]);
  const db = join(root, 'db/published_track.db');
  const sql = text => run('sqlite3', ['-json', db, text]);
  sql("INSERT INTO pub_douyin(id,title,content_type,source_folder,publish_url,publish_date) VALUES(1,'test','post','test','https://www.douyin.com/note/123','2026-09-19');");
  const fetch = fixture => {
    writeFileSync(join(root, 'fixture.json'), JSON.stringify(fixture));
    run('bash', [join(scripts, 'fetch-and-update-metrics.sh'), '--platform', 'douyin', '--id', '1']);
    return JSON.parse(sql('SELECT plays,likes,comments,shares,favorites,deep_metrics FROM pub_douyin WHERE id=1'))[0];
  };
  let row = fetch({ public: { play_count: 0, digg_count: 99 }, creator: {
    view_count: 187, like_count: 7, comment_count: 2, share_count: 3, favorite_count: 1,
    completion_rate: 0.35, danmaku_count: 4, subscribe_count: 2,
  }});
  assert.deepEqual(row, { plays:187, likes:7, comments:2, shares:3, favorites:1,
    deep_metrics: JSON.stringify({completion_rate:0.35, danmaku_count:4, subscribe_count:2}) });
  row = fetch({ public: { digg_count: 99 }, creator: {view_count:0,like_count:0,comment_count:0,share_count:0,favorite_count:0} });
  assert.deepEqual(row, {plays:0,likes:0,comments:0,shares:0,favorites:0,deep_metrics:'{}'});
  sql('UPDATE pub_douyin SET plays=55,likes=1,comments=6,shares=8,favorites=9');
  row = fetch({public:{play_count:0,digg_count:3},creator:null});
  assert.equal(row.plays,55);
  assert.equal(row.likes,3);
  assert.equal(row.comments,6);
  assert.equal(row.shares,8);
  assert.equal(row.favorites,9);
  row = fetch({public:{digg_count:4,comment_count:2},creator:{view_count:60,like_count:null,share_count:-1}});
  assert.equal(row.likes,4);
  assert.equal(row.comments,2);
  assert.equal(row.shares,8);
  assert.equal(row.plays,60);
  assert.equal(row.deep_metrics,'{}');
  console.log('PASS: creator metrics, deep separation, zero updates, missing/invalid values, public fallback');
} finally {
  rmSync(root, {recursive:true,force:true});
}
