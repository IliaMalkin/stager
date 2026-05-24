import { NextRequest, NextResponse } from 'next/server';
import { exportCsvUrl, exportXlsxUrl, fetchApiBlob } from '@/lib/api';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const id = Number(params.id);
  const format = request.nextUrl.searchParams.get('format') === 'xlsx' ? 'xlsx' : 'csv';
  const path = format === 'xlsx' ? exportXlsxUrl(id) : exportCsvUrl(id);
  const upstream = await fetchApiBlob(path);
  if (!upstream.ok) {
    return NextResponse.json({ error: 'upstream failed' }, { status: upstream.status });
  }
  const buf = await upstream.arrayBuffer();
  return new NextResponse(buf, {
    status: 200,
    headers: {
      'Content-Type': upstream.headers.get('Content-Type') || 'application/octet-stream',
      'Content-Disposition':
        upstream.headers.get('Content-Disposition') ||
        `attachment; filename="project-${id}.${format}"`,
    },
  });
}
