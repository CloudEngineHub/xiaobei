import test from 'node:test'
import assert from 'node:assert/strict'
import { parseXhsNoteFromHtml, fetchXhsNoteFromHtml, XhsSecurityBlockError } from '../../crews/main/skills/_shared/xhs-html-note.ts'
import { collectComments } from '../../crews/main/skills/expert-douyin/tools/douyin-comments/scripts/fetch_comments.ts'

function html(stream: unknown, extra='') {
  return `<script>window.__INITIAL_STATE__=${JSON.stringify({note:{noteDetailMap:{abc:{note:{
    type:'video',title:'Test',video:{media:{stream},capa:{duration:3}},
  }}}}})}</script>${extra}`
}

test('XHS EF/unknown buckets, numeric strings and camel/snake keys', () => {
  const note=parseXhsNoteFromHtml(html({h264:[], EF4:[null,{master_url:'https://cdn/720',height:'720'}],
    EF7:[{masterUrl:'https://cdn/1080-low',height:1080,avgBitrate:'100'},
      {master_url:'https://cdn/1080-high',height:'1080',avg_bitrate:'200'}],
    unknown:[{masterUrl:'javascript:bad',height:4000}], metadata:{height:9000}}),'abc')!
  assert.equal(note.videoUrl,'https://cdn/1080-high')
  assert.equal(note.durationMs,3000)
})
test('XHS h265 survives empty h264; malformed buckets use og video', () => {
  assert.equal(parseXhsNoteFromHtml(html({h264:[],h265:[{masterUrl:'//cdn/video'}]}),'abc')?.videoUrl,'https://cdn/video')
  assert.equal(parseXhsNoteFromHtml(html({EF5:null},'<meta property="og:video" content="https://cdn/og">'),'abc')?.videoUrl,'https://cdn/og')
})
test('XHS content containing soft-block words is not a blocked page', () => {
  const body=html({EF4:[{masterUrl:'https://cdn/ok'}]}).replace('Test','安全限制')
  assert.equal(parseXhsNoteFromHtml(body,'abc')?.title,'安全限制')
})
test('OpenCLI soft-block cooldown stays bounded to one retry', async () => {
  const originalFetch=globalThis.fetch
  const originalTimeout=globalThis.setTimeout
  let calls=0
  globalThis.fetch=async () => {calls++; return new Response('安全限制',{status:200})}
  globalThis.setTimeout=((callback: (...args: unknown[])=>void) => {
    queueMicrotask(callback)
    return 0
  }) as unknown as typeof setTimeout
  try {
    await assert.rejects(fetchXhsNoteFromHtml('abc',{xsecToken:'token'}),XhsSecurityBlockError)
    assert.equal(calls,2)
  } finally {globalThis.fetch=originalFetch; globalThis.setTimeout=originalTimeout}
})
const item=(cid:string)=>({cid,text:cid})
const page=(comments:unknown[],cursor=0,has_more=0,total=0)=>({ok:true,status:200,data:{status_code:0,comments,cursor,has_more,total}}) as any

test('Douyin HTTP 200 empty body and status 8 are not expired login and do not retry',async()=>{
  for (const response of [{ok:true,status:200,data:null}, {ok:true,status:200,data:{status_code:8}}]) {
    let calls=0
    const result=await collectComments('123',40,async()=>{calls++;return response})
    assert.equal(result.ok,false)
    assert.match(result.error!,/^COMMENT_API_UNAVAILABLE/)
    assert.equal(calls,1)
  }
})
test('Douyin deduplicates, retains partial comments and stops stalled cursor',async()=>{
  let calls=0; const waits:number[]=[]
  const result=await collectComments('123',40,async()=>++calls===1
    ?page([item('a')],20,1,100):page([item('a')],20,1,100),async ms=>{waits.push(ms)})
  assert.equal(result.ok,false)
  assert.equal(result.fetched,1)
  assert.match(result.error!,/PAGINATION_STALLED/)
  assert.equal(calls,2)
  assert.equal(waits.length,1)
  assert.ok(waits[0]>=1000 && waits[0]<3000)
})
test('Douyin true empty is valid, positive-total empty is not',async()=>{
  assert.equal((await collectComments('123',40,async()=>page([]))).ok,true)
  assert.equal((await collectComments('123',40,async()=>page([],0,0,10))).ok,false)
  assert.equal((await collectComments('123',40,async()=>({ok:true,status:200,data:{status_code:0,comments:[]}}))).ok,false)
})
test('Douyin keeps final page, marks limit truncation and preserves request failure',async()=>{
  assert.equal((await collectComments('123',40,async()=>page([item('a')],0,0,1))).fetched,1)
  assert.equal((await collectComments('123',1,async()=>page([item('a')],20,1,10))).truncated,true)
  assert.match((await collectComments('123',40,async()=>{throw new Error('network')})).error!,/COMMENT_REQUEST_FAILED: network/)
})
