export default function NotFound() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[#0D1B2A]">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-white">404</h1>
        <p className="mt-4 text-slate-400">Page not found</p>
        <a
          href="/"
          className="mt-6 inline-block rounded-lg bg-blue-500 px-4 py-2 text-sm text-white hover:bg-blue-600"
        >
          Go home
        </a>
      </div>
    </div>
  );
}
