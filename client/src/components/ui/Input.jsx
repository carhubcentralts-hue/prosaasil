export default function Input({label, error, ...props}){
  return (
    <div className="space-y-1">
      {label && <label className="text-sm">{label}</label>}
      <input {...props}
        className={`w-full px-3 py-2 border rounded-xl min-h-[44px] bg-white focus:outline-none focus:ring-2 focus:ring-accent-500 ${error?'border-red-400':'border-gray-300'}`} />
      {error && <div className="text-xs text-red-600">{error}</div>}
    </div>
  );
}