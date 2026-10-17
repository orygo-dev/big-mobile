import {beforeEach, describe, expect, it} from 'vitest';
import {syncBrandingMetadata} from './branding';

describe('installation branding metadata',()=>{
 beforeEach(()=>{document.head.innerHTML='';});
 it('uses configured name for title and installation labels and real API icons',()=>{
  syncBrandingMetadata({app_name:'Klik BIG',logo:'logo-one'});
  expect(document.title).toBe('Klik BIG');
  expect(document.querySelector('meta[name="application-name"]').content).toBe('Klik BIG');
  expect(document.querySelector('meta[name="apple-mobile-web-app-title"]').content).toBe('Klik BIG');
  expect(document.querySelector('link[rel="manifest"]').href).toContain('/api/branding/manifest.webmanifest?v=');
  expect(document.querySelector('link[rel="icon"]').href).toContain('/api/branding/icon/32.png?v=');
  expect(document.querySelector('link[rel="apple-touch-icon"]').href).toContain('/api/branding/icon/180.png?v=');
 });
 it('refreshes icon and manifest versions after a new logo without duplicating tags',()=>{
  syncBrandingMetadata({app_name:'App',logo:'logo-one'});
  const previous=document.querySelector('link[rel="manifest"]').href;
  syncBrandingMetadata({app_name:'App',logo:'logo-two'});
  expect(document.querySelector('link[rel="manifest"]').href).not.toBe(previous);
  expect(document.querySelectorAll('link[rel="manifest"]').length).toBe(1);
  expect(document.querySelectorAll('link[rel="icon"]').length).toBe(1);
 });
});
