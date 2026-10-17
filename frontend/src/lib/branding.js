import { API } from "@/lib/api";

// Revision is a cache hint, not a security identifier.
function revision(text) {
  let hash = 2166136261;
  for (let i=0; i<text.length; i++) hash=Math.imul(hash ^ text.charCodeAt(i),16777619);
  return (hash >>> 0).toString(16);
}
function link(rel, href, type, sizes) {
  let node=document.head.querySelector(`link[rel="${rel}"]`);
  if (!node) {node=document.createElement("link");node.rel=rel;document.head.appendChild(node);}
  node.href=href;
  if (type) node.type=type;
  if (sizes) node.setAttribute("sizes",sizes);
}
function meta(name, content) {
  let node=document.head.querySelector(`meta[name="${name}"]`);
  if (!node) {node=document.createElement("meta");node.name=name;document.head.appendChild(node);}
  node.content=content;
}
export function syncBrandingMetadata(data) {
  const name=data.app_name || "BIG Mobile";
  const version=revision(name+"\0"+(data.logo||""));
  document.title=name;
  meta("application-name",name);
  meta("apple-mobile-web-app-title",name);
  link("manifest",`${API}/branding/manifest.webmanifest?v=${version}`,"application/manifest+json");
  link("icon",`${API}/branding/icon/32.png?v=${version}`,"image/png","32x32");
  link("apple-touch-icon",`${API}/branding/icon/180.png?v=${version}`,"image/png","180x180");
}
