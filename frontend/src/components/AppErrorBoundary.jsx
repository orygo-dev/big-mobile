import { Component } from "react";

export default class AppErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <main className="min-h-screen grid place-items-center bg-blue-50 p-6"><div className="rounded-2xl bg-white p-8 shadow-sm text-center"><h1 className="text-xl font-semibold">Halaman belum dapat dimuat</h1><p className="mt-3 text-slate-600">Periksa koneksi, lalu muat ulang aplikasi. Perubahan formulir yang belum dikirim mungkin perlu diisi kembali.</p><button className="mt-6 rounded-xl bg-blue-600 px-6 py-3 text-white" onClick={() => window.location.reload()}>Muat ulang</button></div></main>;
    return this.props.children;
  }
}
