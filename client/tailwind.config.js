export default {
  content: ["./index.html","./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      borderRadius:{'2xl':'1rem'},
      colors:{ 
        brand:{900:"#0f172a"}, 
        accent:{500:"#6366f1"} 
      },
      boxShadow:{ 
        soft:"0 8px 28px rgba(0,0,0,.08)" 
      }
    }
  },
  plugins:[]
}