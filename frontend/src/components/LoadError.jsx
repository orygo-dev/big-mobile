export default function LoadError({ message, onRetry }) {
  return <div role="alert" className="rounded-xl border border-orange-200 bg-orange-50 p-5 text-slate-800"><p>{message}</p><button onClick={onRetry} className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-white">Coba lagi</button></div>;
}
