"""Read-only month-to-date comparisons; existing finance totals and writes are unchanged."""
import calendar
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal, ROUND_HALF_UP
from fastapi import Depends
from finance import date_bounds

WIB=timezone(timedelta(hours=7))
def today():return datetime.now(WIB).date()

def comparison(current,previous):
    delta=current-previous
    percentage=(delta/abs(previous)*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if previous else (Decimal('0') if not current else None)
    return {'current':format(current,'.2f'),'previous':format(previous,'.2f'),'percentage':format(percentage or Decimal('0'),'.2f') if percentage is not None else None,'direction':'UP' if delta>0 else 'DOWN' if delta<0 else 'UNCHANGED','baseline_zero':not previous}

def summarize(rows,day):
    first=day.replace(day=1);prior=(first-timedelta(days=1)).replace(day=1)
    previous_end=prior.replace(day=min(day.day,calendar.monthrange(prior.year,prior.month)[1]))
    buckets={}
    for stamp,direction,amount in rows:
        bucket=buckets.setdefault(str(stamp)[:10],{'PEMASUKAN':Decimal('0'),'PENGELUARAN':Decimal('0')})
        if direction in bucket:bucket[direction]+=Decimal(str(amount))
    def totals(start,end):
        income=sum((values['PEMASUKAN'] for stamp,values in buckets.items() if start.isoformat()<=stamp<=end.isoformat()),Decimal('0'))
        expense=sum((values['PENGELUARAN'] for stamp,values in buckets.items() if start.isoformat()<=stamp<=end.isoformat()),Decimal('0'))
        return {'income':income,'expense':expense,'profit':income-expense}
    current=totals(first,day);previous=totals(prior,previous_end)
    series=[];income=expense=Decimal('0')
    for n in range(day.day):
        stamp=(first+timedelta(days=n)).isoformat();values=buckets.get(stamp,{})
        income+=values.get('PEMASUKAN',Decimal('0'));expense+=values.get('PENGELUARAN',Decimal('0'))
        series.append({'date':stamp,'income':format(income,'.2f'),'expense':format(expense,'.2f'),'profit':format(income-expense,'.2f')})
    return {'month':first.isoformat()[:7],'previous_month':prior.isoformat()[:7],'timezone':'Asia/Jakarta','current_start':first.isoformat(),'current_end':day.isoformat(),'previous_start':prior.isoformat(),'previous_end':previous_end.isoformat(),'metrics':{key:comparison(current[key],previous[key]) for key in current},'series':series}

def register(router,runtime):
    @router.get('/dashboard/finance-trends')
    async def trends(user:dict=Depends(runtime.admin_required)):
        day=today();previous=(day.replace(day=1)-timedelta(days=1)).replace(day=1)
        start,end=date_bounds(previous.isoformat(),day.isoformat())
        rows=await runtime.db.finance_daily(user['company_id'],start,end)
        return summarize(rows,day)
