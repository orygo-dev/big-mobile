// Private test fixture only; pytest creates and removes its isolated SQL database.
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
let dropNextChatAcknowledgement=false;
let dropNextReportAcknowledgement=false,dropNextPaymentAcknowledgement=false;
const server=https.createServer({key:fs.readFileSync(fixture.key),cert:fs.readFileSync(fixture.cert)},(incoming,outgoing)=>{
  if(incoming.url.startsWith('/api/')){
    const chatDrop=dropNextChatAcknowledgement&&incoming.method==='POST'&&/^\/api\/chat\/[^/]+\/messages$/.test(incoming.url);
    const reportDrop=dropNextReportAcknowledgement&&incoming.method==='POST'&&incoming.url==='/api/laporan';
    const paymentDrop=dropNextPaymentAcknowledgement&&incoming.method==='POST'&&/^\/api\/laporan\/[^/]+\/payment$/.test(incoming.url);
    const drop=chatDrop||reportDrop||paymentDrop;
    if(chatDrop)dropNextChatAcknowledgement=false;
    if(reportDrop)dropNextReportAcknowledgement=false;
    if(paymentDrop)dropNextPaymentAcknowledgement=false;
    const upstream=http.request({hostname:apiURL.hostname,port:apiURL.port,path:incoming.url,method:incoming.method,headers:incoming.headers},response=>{
      if(drop&&response.statusCode===200){response.resume();response.on('end',()=>{outgoing.writeHead(502,{'content-type':'application/json'});outgoing.end(JSON.stringify({detail:chatDrop?'QA chat acknowledgement lost':'QA report/payment acknowledgement lost'}));});}
      else{outgoing.writeHead(response.statusCode,response.headers);response.pipe(outgoing);}
    });
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
  const teammate=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:390,height:844}});
  const ap=await admin.newPage(),op=await officer.newPage(),tp=await teammate.newPage();const errors=[];ap.on('pageerror',error=>errors.push(error.message));op.on('pageerror',error=>errors.push(error.message));tp.on('pageerror',error=>errors.push(error.message));
  async function login(page,email,destination){await page.goto(origin+'/login');await page.getByTestId('login-email-input').fill(email);await page.getByTestId('login-password-input').fill(fixture.password);await page.getByTestId('login-submit-button').click();await page.waitForURL('**/'+destination);assert.equal(await page.evaluate(()=>localStorage.getItem('fc_token')),null);}
  await login(ap,fixture.admin_email,'admin');await login(op,fixture.officer_email,'app');await login(tp,fixture.teammate_email,'app');
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
  await ap.getByTestId('penugasan-petugas-select').click();await ap.getByRole('option').filter({hasText:'QA other'}).click();
  assert.equal(await ap.getByTestId('penugasan-selected-officers').getByRole('button',{name:/Hapus/}).count(),2);
  await ap.screenshot({path:path.join(path.dirname(fixture.print_pdf),'team-assignment-form.png'),fullPage:true});
  let pending=ap.waitForResponse(response=>response.url().endsWith('/api/penugasan')&&response.request().method()==='POST');await ap.getByTestId('penugasan-submit-button').click();const assigned=await pending;assert.equal(assigned.status(),200);const letter=await assigned.json();
  assert.equal(letter.status,'menunggu_approval');
  const approval=await direct.post('penugasan/'+letter.assignment_id+'/approve',{headers:{Authorization:'Bearer '+fixture.owner_token}});assert.equal(approval.status(),200);
  assert.equal(letter.petugas_count,2);await ap.getByRole('button',{name:'Tutup',exact:true}).click();
  await ap.getByTestId('penugasan-officer-count-'+letter.id).waitFor();assert.equal(await ap.getByTestId('penugasan-officer-count-'+letter.id).innerText(),'2 Petugas');
  await tp.goto(origin+'/app/tugas/'+unit.id);await tp.getByTestId('detail-tugas-surat-penugasan').click();
  await tp.getByTestId('doc-page-1').waitFor();assert.equal(await tp.locator('.field-officer tbody tr').count(),2);assert.equal(await tp.getByTestId('assignment-recipient').count(),2);assert.equal(await tp.getByTestId('doc-cancel-button').count(),0);
  await tp.screenshot({path:path.join(path.dirname(fixture.print_pdf),'team-assignment-letter.png'),fullPage:true});
  await op.goto(origin+'/app/tugas/'+unit.id);const authority=op.getByTestId('detail-tugas-surat-kuasa');await authority.waitFor();assert.equal((await officer.request.get(origin+await authority.getAttribute('href'))).status(),200);
  for(const [page,base] of [[ap,'/admin'],[op,'/app'],[tp,'/app']]) {
    await page.goto(origin+base+'/chat');await page.getByTestId('chat-new-message').click();
    await page.getByTestId('chat-start-'+letter.assignment_id).waitFor();
    await page.screenshot({path:path.join(path.dirname(fixture.print_pdf),base==='/admin'?'chat-new-admin.png':'chat-new-officer.png'),fullPage:true});
    await page.getByTestId('chat-start-'+letter.assignment_id).click();await page.getByTestId('chat-composer').waitFor();
  }
  // Browsers without randomUUID (including insecure contexts) must still send.
  await op.evaluate(()=>{Object.defineProperty(window.crypto,'randomUUID',{value:undefined,configurable:true});});
  await op.getByTestId('chat-text').fill('Koordinasi chat browser QA');
  await op.getByTestId('chat-file-input').setInputFiles([fixture.image,fixture.pdf]);
  await op.evaluate(()=>{window.__qaGeo=navigator.geolocation.getCurrentPosition;navigator.geolocation.getCurrentPosition=(_,failure)=>failure({code:1});});
  await op.getByTestId('chat-share-location').click();await op.getByRole('alert').filter({hasText:'Lokasi belum tersedia'}).waitFor();
  await op.evaluate(()=>{navigator.geolocation.getCurrentPosition=window.__qaGeo;delete window.__qaGeo;});
  await op.getByTestId('chat-share-location').click();await op.getByTestId('chat-location-preview').waitFor();
  // Proxy keeps the actual binary file bytes; CDP route.fetch omits disk-upload bytes.
  dropNextChatAcknowledgement=true;
  await op.getByTestId('chat-send').click();await op.getByRole('alert').filter({hasText:'QA chat acknowledgement lost'}).waitFor();assert.equal(await op.getByTestId('chat-text').inputValue(),'Koordinasi chat browser QA');
  pending=op.waitForResponse(response=>response.url().endsWith('/messages')&&response.request().method()==='POST'&&response.status()===200);await op.getByTestId('chat-send').click();await pending;
  await op.getByTestId('chat-attachment-image').locator('img').evaluate(image=>image.decode());await op.getByTestId('chat-location').waitFor();
  let chat=await api('GET','chat/'+letter.assignment_id);assert.equal(chat.messages.length,1);assert.equal(chat.messages[0].attachments.length,2);assert.equal(chat.unread,1);
  await ap.goto(origin+'/admin/chat');await ap.getByTestId('chat-inbox-'+letter.assignment_id).click();await ap.getByText('Koordinasi chat browser QA',{exact:true}).waitFor();await ap.getByTestId('chat-attachment-image').locator('img').evaluate(image=>image.decode());
  const chatFile=await ap.getByTestId('chat-attachment-document').getAttribute('href');assert.equal((await admin.request.get(origin+chatFile)).status(),200);
  await ap.getByTestId('chat-text').fill('Arahan admin melalui chat');pending=ap.waitForResponse(response=>response.url().endsWith('/messages')&&response.request().method()==='POST');await ap.getByTestId('chat-send').click();assert.equal((await pending).status(),200);
  await op.getByText('Arahan admin melalui chat',{exact:true}).waitFor();
  await tp.getByText('Arahan admin melalui chat',{exact:true}).waitFor();
  await tp.getByTestId('chat-text').fill('Koordinasi anggota kedua');pending=tp.waitForResponse(response=>response.url().endsWith('/messages')&&response.request().method()==='POST');await tp.getByTestId('chat-send').click();assert.equal((await pending).status(),200);await op.getByText('Koordinasi anggota kedua',{exact:true}).waitFor();
  await ap.screenshot({path:path.join(path.dirname(fixture.print_pdf),'chat-admin.png'),fullPage:true});
  await op.screenshot({path:path.join(path.dirname(fixture.print_pdf),'chat-officer.png'),fullPage:true});
  const chatReadURL=url=>url.pathname===`/api/chat/${letter.assignment_id}`;
  await op.route(chatReadURL,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA chat read failure'})}));
  await op.reload();await op.getByRole('alert').filter({hasText:'QA chat read failure'}).waitFor();assert.equal(await op.getByTestId('chat-composer').count(),0);
  await op.unroute(chatReadURL);await op.getByRole('button',{name:'Coba lagi',exact:true}).click();await op.getByText('Arahan admin melalui chat',{exact:true}).waitFor();
  await op.goto(origin+'/app/tugas/'+unit.id+'/laporan');await op.waitForURL('**/app/riwayat');assert.equal(await op.getByTestId('petugas-submit-report-button').count(),0);
  await ap.goto(origin+'/admin/laporan');await ap.getByTestId('laporan-create-button').click();await ap.getByTestId('admin-report-assignment').click();await ap.getByRole('option').filter({hasText:letter.document_number}).click();
  await ap.getByTestId('admin-report-photos').setInputFiles([fixture.image,fixture.image]);await ap.getByTestId('admin-report-amount').fill('750000');await ap.getByTestId('admin-report-notes').fill('Bukti kegiatan lapangan dicatat oleh admin');
  dropNextReportAcknowledgement=true;await ap.getByTestId('admin-report-submit').click();await ap.waitForURL('**/admin/laporan/*');
  await ap.getByTestId('laporan-photo-0').locator('img').evaluate(image=>image.decode());await ap.getByTestId('laporan-photo-1').locator('img').evaluate(image=>image.decode());
  assert((await ap.getByTestId('payment-amount').innerText()).includes('750.000'));assert((await ap.getByTestId('payment-status').first().innerText()).includes('Menunggu Pembayaran'));
  const reports=await api('GET','laporan');const report=reports.find(item=>item.account_id===unit.id);assert(report);assert.equal(report.payment_status,'MENUNGGU_PEMBAYARAN');assert.equal(reports.filter(item=>item.assignment_id===letter.assignment_id).length,1);
  await ap.getByTestId('laporan-review-input').fill('Review browser QA');pending=ap.waitForResponse(response=>response.url().endsWith('/review')&&response.request().method()==='PATCH');await ap.getByTestId('laporan-review-save').click();assert.equal((await pending).status(),200);
  for(const page of [op,tp]) {await page.goto(origin+'/app/riwayat');const card=page.getByTestId('riwayat-card-'+report.id);await card.getByText('Review browser QA').waitFor();assert((await card.getByTestId('payment-status').innerText()).includes('Menunggu Pembayaran'));await card.locator('img[src*="/api/files/"]').first().evaluate(image=>image.decode());}
  await ap.goto(origin+'/admin/laporan');await ap.getByTestId('laporan-pay-'+report.id).click();await ap.getByTestId('payment-proof-input').setInputFiles(fixture.pdf);
  dropNextPaymentAcknowledgement=true;await ap.getByTestId('payment-save').click();await ap.getByTestId('payment-proof-link').waitFor();
  const paid=await api('GET','laporan/'+report.id);assert.equal(paid.payment_status,'SELESAI');assert.equal(paid.payment_amount,'750000.00');assert.equal(paid.photos.length,2);
  for(const page of [op,tp]) {await page.goto(origin+'/app/riwayat');const card=page.getByTestId('riwayat-card-'+report.id);await card.getByTestId('payment-proof-link').waitFor();assert.equal(await card.getByTestId('payment-status').innerText(),'Selesai');const href=await card.getByTestId('payment-proof-link').getAttribute('href');assert.equal((await page.request.get(origin+href)).status(),200);}
  await ap.screenshot({path:path.join(path.dirname(fixture.print_pdf),'admin-report-paid.png'),fullPage:true});await op.screenshot({path:path.join(path.dirname(fixture.print_pdf),'officer-report-paid.png'),fullPage:true});
  await api('PATCH','surat-tugas/'+letter.id+'/status',{status:'selesai'});
  await op.goto(origin+'/app/chat/'+letter.assignment_id);await op.getByTestId('chat-read-only').waitFor();assert.equal(await op.getByTestId('chat-composer').count(),0);await op.getByText('Arahan admin melalui chat',{exact:true}).waitFor();
  const settings={...await api('GET','company'),nama:'PT Reborn Browser QA',alamat:'Jl. Kantor Browser QA 12',email:'office@browser-qa.example.com',telepon:'021-987654'};
  await api('PUT','company',settings);
  const logoUpload=await admin.request.post(origin+'/api/company/logo',{headers:{Origin:origin},multipart:{file:{name:'company.png',mimeType:'image/png',buffer:fs.readFileSync(fixture.image)}}});assert.equal(logoUpload.status(),200);
  const configured=await logoUpload.json();
  async function verifyLetterhead(page) {
    const headers=page.getByTestId('company-letterhead');
    await headers.first().waitFor();
    for(const header of await headers.all()) {
      const text=await header.innerText();
      for(const value of [settings.nama,settings.alamat,settings.email,settings.telepon])assert(text.includes(value));
      assert.equal(await header.locator('img').getAttribute('src'),configured.logo);
      await header.locator('img').evaluate(image=>image.decode());
    }
  }
  await ap.goto(origin+'/admin/surat-tugas/'+letter.id+'/dokumen');
  await ap.getByTestId('doc-page-1').waitFor();await verifyLetterhead(ap);
  assert.equal(await ap.getByTestId('company-letterhead').count(),2);
  await ap.goto(origin+'/admin/surat-tugas/'+letter.id+'/print');await ap.getByText(unit.nama_debitur,{exact:false}).first().waitFor();
  await verifyLetterhead(ap);
  await ap.pdf({path:fixture.print_pdf,format:'A4',printBackground:true});
  await ap.route('**/api/dashboard/stats',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA dashboard failure'})}));await ap.goto(origin+'/admin');await ap.getByRole('alert').filter({hasText:'QA dashboard failure'}).waitFor();assert.equal(await ap.getByTestId('dashboard-stats').count(),0);await ap.unroute('**/api/dashboard/stats');await ap.getByRole('button',{name:'Coba lagi',exact:true}).click();await ap.getByTestId('dashboard-stats').waitFor();
  await op.goto(origin+'/app/profil');await op.getByTestId('petugas-logout-button').click();await op.waitForURL('**/login');assert.equal((await officer.request.get(origin+'/api/auth/me')).status(),401);
  assert.equal(errors.length,0);
  console.log('PASS HTTPS UI: assignment, chat photo/document/location, chat lost acknowledgement retry, closed chat history, admin report/team payment, report/payment lost acknowledgement, read failure/retry, review/history, print, secure cookie and logout.');
} finally {
  await direct.dispose();await browser.close();await new Promise(resolve=>server.close(resolve));
}
