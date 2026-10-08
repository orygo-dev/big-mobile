// Private test fixture only; pytest creates and removes its isolated Mongo database.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import https from 'node:https';
import assert from 'node:assert/strict';
import { chromium, request } from '@playwright/test';

const fixture=JSON.parse(fs.readFileSync(process.env.E2E_FIXTURE_PATH,'utf8'));
const root=path.resolve(import.meta.dirname,'../build');
const origin=`https://localhost:${fixture.web_port}`;
const apiURL=new URL(fixture.api_url);
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml'};
const server=https.createServer({key:fs.readFileSync(fixture.key),cert:fs.readFileSync(fixture.cert)},(incoming,outgoing)=>{
  if(incoming.url.startsWith('/api/')){
    const upstream=http.request({hostname:apiURL.hostname,port:apiURL.port,path:incoming.url,method:incoming.method,headers:incoming.headers},response=>{outgoing.writeHead(response.statusCode,response.headers);response.pipe(outgoing);});
    upstream.on('error',()=>{outgoing.writeHead(503);outgoing.end();});incoming.pipe(upstream);return;
  }
  let file=path.resolve(root,'.'+new URL(incoming.url,origin).pathname);
  if(!file.startsWith(root+path.sep)){outgoing.writeHead(403);outgoing.end();return;}
  if(!fs.existsSync(file)||!fs.statSync(file).isFile())file=path.join(root,'index.html');
  outgoing.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');
  const stream=fs.createReadStream(file);stream.on('error',()=>outgoing.destroy());stream.pipe(outgoing);
});
await new Promise(resolve=>server.listen(fixture.web_port,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true,...(process.env.TEST_BROWSER_CHANNEL?{channel:process.env.TEST_BROWSER_CHANNEL}:{})});
const direct=await request.newContext({baseURL:fixture.api_url+'/'});
async function api(method,url,data,expected=200){const response=await direct.fetch(url,{method,data,headers:{Authorization:'Bearer '+fixture.admin_token}});assert.equal(response.status(),expected);return response.json();}
try {
  const admin=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}});
  const officer=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:390,height:844},geolocation:{latitude:-6.2,longitude:106.8},permissions:['geolocation']});
  const ap=await admin.newPage(),op=await officer.newPage();const errors=[];ap.on('pageerror',error=>errors.push(error.message));op.on('pageerror',error=>errors.push(error.message));
  async function login(page,email,destination){await page.goto(origin+'/login');await page.getByTestId('login-email-input').fill(email);await page.getByTestId('login-password-input').fill(fixture.password);await page.getByTestId('login-submit-button').click();await page.waitForURL('**/'+destination);assert.equal(await page.evaluate(()=>localStorage.getItem('fc_token')),null);}
  await login(ap,fixture.admin_email,'admin');await login(op,fixture.officer_email,'app');
  const cookie=(await admin.cookies()).find(item=>item.name==='fc_session');assert(cookie?.secure&&cookie?.httpOnly);
  await op.route('**/api/my/tugas',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA gangguan jaringan'})}));
  await op.goto(origin+'/app/tugas');await op.getByRole('alert').filter({hasText:'QA gangguan jaringan'}).waitFor();assert.equal(await op.getByText('Belum ada tugas',{exact:true}).count(),0);
  await op.unroute('**/api/my/tugas');await op.getByRole('button',{name:'Coba lagi',exact:true}).click();await op.getByRole('alert').waitFor({state:'hidden'});
  const suffix=Date.now().toString();
  const client=await api('POST','clients',{nama_perusahaan:'Browser QA '+suffix});
  const sk=await api('POST','surat-kuasa',{nomor:'Browser '+suffix,client_id:client.id,tanggal_berlaku:'2020-01-01',tanggal_berakhir:'2099-12-31'});
  const pdf=await direct.post('surat-kuasa/'+sk.id+'/file',{headers:{Authorization:'Bearer '+fixture.admin_token},multipart:{file:{name:'authority.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(fixture.pdf)}}});assert.equal(pdf.status(),200);
  const unit=await api('POST','akun',{nomor_kontrak:suffix,nama_debitur:'Browser Debitur '+suffix,client_id:client.id,surat_kuasa_id:sk.id});
  await ap.goto(origin+'/admin/penugasan');await ap.getByTestId('penugasan-create-button').click();await ap.getByTestId('penugasan-unit-select').click();await ap.getByRole('option').filter({hasText:unit.nama_debitur}).click();await ap.getByTestId('penugasan-petugas-select').click();await ap.getByRole('option').filter({hasText:'QA officer'}).click();
  let pending=ap.waitForResponse(response=>response.url().endsWith('/api/penugasan')&&response.request().method()==='POST');await ap.getByTestId('penugasan-submit-button').click();const assigned=await pending;assert.equal(assigned.status(),200);const letter=await assigned.json();
  await op.goto(origin+'/app/tugas/'+unit.id);const authority=op.getByTestId('detail-tugas-surat-kuasa');await authority.waitFor();assert.equal((await officer.request.get(origin+await authority.getAttribute('href'))).status(),200);
  await op.goto(origin+'/app/tugas/'+unit.id+'/laporan');await op.getByTestId('laporan-status-UNIT_DITEMUKAN').click();await op.getByTestId('laporan-catatan-input').fill('Kunjungan browser QA dengan foto dan GPS');await op.getByText('Terdeteksi',{exact:true}).waitFor();await op.getByTestId('laporan-next-button').click();await op.getByTestId('laporan-photo-input').setInputFiles(fixture.image);await op.getByTestId('laporan-photo-preview-0').waitFor();await op.getByTestId('laporan-next-button').click();
  // Simulate a lost acknowledgement after the API has committed the report.
  await op.route('**/api/laporan',async route=>{const response=await route.fetch();assert.equal(response.status(),200);await route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'QA acknowledgement lost'})});});
  await op.getByTestId('petugas-submit-report-button').click();await op.getByTestId('laporan-done-home').waitFor();await op.unroute('**/api/laporan');
  const reports=await api('GET','laporan');const report=reports.find(item=>item.account_id===unit.id);assert(report);
  await ap.goto(origin+'/admin/laporan/'+report.id);await ap.getByTestId('laporan-photo-0').locator('img').evaluate(image=>image.decode());await ap.getByTestId('laporan-review-input').fill('Review browser QA');pending=ap.waitForResponse(response=>response.url().endsWith('/review')&&response.request().method()==='PATCH');await ap.getByTestId('laporan-review-save').click();assert.equal((await pending).status(),200);
  await op.goto(origin+'/app/riwayat');await op.getByText('Review browser QA').waitFor();await op.locator('img[src*="/api/files/"]').first().evaluate(image=>image.decode());
  await api('PATCH','surat-tugas/'+letter.id+'/status',{status:'selesai'});
  await ap.goto(origin+'/admin/surat-tugas/'+letter.id+'/print');await ap.getByText(unit.nama_debitur,{exact:false}).first().waitFor();
  await ap.pdf({path:fixture.print_pdf,format:'A4',printBackground:true});
  await ap.route('**/api/dashboard/stats',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA dashboard failure'})}));await ap.goto(origin+'/admin');await ap.getByRole('alert').filter({hasText:'QA dashboard failure'}).waitFor();assert.equal(await ap.getByTestId('dashboard-stats').count(),0);await ap.unroute('**/api/dashboard/stats');await ap.getByRole('button',{name:'Coba lagi',exact:true}).click();await ap.getByTestId('dashboard-stats').waitFor();
  await op.goto(origin+'/app/profil');await op.getByTestId('petugas-logout-button').click();await op.waitForURL('**/login');assert.equal((await officer.request.get(origin+'/api/auth/me')).status(),401);
  assert.equal(errors.length,0);
  console.log('PASS HTTPS UI: assignment, photo/GPS, lost acknowledgement, read failure/retry, review/history, print, secure cookie and logout.');
} finally {
  await direct.dispose();await browser.close();await new Promise(resolve=>server.close(resolve));
}
