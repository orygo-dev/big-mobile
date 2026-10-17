"""Read-only cash movement report, derived from authoritative payment records."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

WIB = timezone(timedelta(hours=7))


def date_bounds(start, end):
    try:
        first = date.fromisoformat(start) if start else None
        last = date.fromisoformat(end) if end else None
        if (first and first.isoformat()!=start) or (last and last.isoformat()!=end):
            raise ValueError()
        if first and last and first > last:
            raise ValueError()
        def utc(day):
            return datetime.combine(day, time.min, WIB).astimezone(timezone.utc).isoformat()
        return utc(first) if first else None, utc(last+timedelta(days=1)) if last else None
    except (ValueError, OverflowError):
        raise HTTPException(400, "Rentang tanggal tidak valid. Gunakan YYYY-MM-DD; tanggal akhir harus setelah atau sama dengan tanggal awal.")


def normalize(result):
    income = result['totals'].get('PEMASUKAN', Decimal('0'))
    expense = result['totals'].get('PENGELUARAN', Decimal('0'))
    rows = []
    for identity, occurred, direction, nominal, record in result['rows']:
        incoming = direction == 'PEMASUKAN'
        rows.append({'id': direction+':'+identity, 'source_id': identity, 'type': direction,
                     'date': occurred, 'amount': format(nominal, '.2f'),
                     'party': record.get('leasing_name', '') if incoming else ', '.join(record.get('team_names') or []) or record.get('petugas_name') or 'Tim petugas',
                     'description': 'Pembayaran leasing' if incoming else record.get('catatan') or 'Pembayaran petugas / tim',
                     'proof_url': record.get('url', '') if incoming else (record.get('payment_proof') or {}).get('url', ''),
                     'source_url': '/admin/pembayaran-leasing' if incoming else '/admin/laporan/'+identity})
    return {'items': rows, 'total': result['count'], 'summary': {'income': format(income, '.2f'), 'expense': format(expense, '.2f'), 'balance': format(income-expense, '.2f')}}


def register(router, runtime):
    async def load(user, start, end, kind, page, limit, export=False):
        first, last = date_bounds(start, end)
        try:
            result = await runtime.db.finance_report(user['company_id'], first, last, kind, page, limit, export)
        except ValueError as error:
            if str(error) != 'EXPORT_LIMIT':raise
            raise HTTPException(400, "Ekspor maksimal 10.000 transaksi. Persempit rentang tanggal.")
        return normalize(result)

    @router.get('/finance')
    async def listing(start: str = '', end: str = '', kind: Literal['', 'PEMASUKAN', 'PENGELUARAN'] = '', page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), user: dict = Depends(runtime.admin_required)):
        data = await load(user, start, end, kind, page, limit)
        return {**data, 'next_page': page+1 if page*limit<data['total'] else None}

    @router.get('/finance/export/{extension}')
    async def export_file(extension: Literal['pdf', 'xlsx'], request: Request, start: str = '', end: str = '', kind: Literal['', 'PEMASUKAN', 'PENGELUARAN'] = '', user: dict = Depends(runtime.admin_required)):
        from finance_exports import render_pdf, render_xlsx
        data = await load(user, start, end, kind, 1, 10000, True)
        company = await runtime.db.companies.find_one({'id': user['company_id']}) or {}
        title = company.get('nama') or 'Laporan Keuangan'
        period = f"{start or 'Awal pencatatan'} s.d. {end or 'Terbaru'} | {kind or 'Semua transaksi'} | WIB"
        content = await run_in_threadpool(render_pdf if extension=='pdf' else render_xlsx, data, title, period)
        await runtime.log_audit(user, 'Mengekspor laporan keuangan '+extension.upper(), 'finance_report', '', request)
        return Response(content, media_type='application/pdf' if extension=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition':f'attachment; filename="laporan-keuangan.{extension}"', 'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'})
