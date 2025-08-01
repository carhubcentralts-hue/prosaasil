import { Route, Switch } from "wouter";
import Dashboard from "./pages/dashboard";
import Customers from "./pages/customers";
import WhatsApp from "./pages/whatsapp";
import AICalls from "./pages/ai-calls";
import NotFound from "./pages/not-found";
import Sidebar from "./components/layout/sidebar";
import { Toaster } from "@/components/ui/toaster";

function App() {
  return (
    <div className="flex h-screen bg-gray-50 text-gray-900" dir="rtl">
      <Sidebar />
      <div className="flex-1 lg:mr-64">
        <Switch>
          <Route path="/" component={Dashboard} />
          <Route path="/customers" component={Customers} />
          <Route path="/whatsapp" component={WhatsApp} />
          <Route path="/ai-calls" component={AICalls} />
          <Route component={NotFound} />
        </Switch>
      </div>
      <Toaster />
    </div>
  );
}

export default App;
