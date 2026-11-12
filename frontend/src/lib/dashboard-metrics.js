export function percentageLabel(metric) {
  if (!metric) return '—';
  if (metric.percentage === null) return 'Baru';
  const value=Number(metric.percentage);
  if(!Number.isFinite(value))return '—';
  return `${value>0?'+':''}${new Intl.NumberFormat('id-ID',{minimumFractionDigits:2,maximumFractionDigits:2}).format(value)}%`;
}
export function sparkline(values) {
 const finite=values.map(Number);
 if(!finite.length||finite.some(value=>!Number.isFinite(value)))return null;
 const min=Math.min(0,...finite),max=Math.max(0,...finite),range=max-min;
 return finite.map((value,index)=>`${(index/(finite.length-1||1)*116+2).toFixed(2)},${(range?46-(value-min)/range*40:26).toFixed(2)}`).join(' ');
}
