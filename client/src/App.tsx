import { Router, Route, Switch } from 'wouter';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import WhatsApp from './pages/WhatsApp';
import AiCalls from './pages/AiCalls';
import Invoices from './pages/Invoices';
import Signatures from './pages/Signatures';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Topbar />
        <main className="flex-1 p-6 overflow-auto">
          <Router>
            <Switch>
              <Route path="/" component={Dashboard} />
              <Route path="/customers" component={Customers} />
              <Route path="/whatsapp" component={WhatsApp} />
              <Route path="/ai-calls" component={AiCalls} />
              <Route path="/invoices" component={Invoices} />
              <Route path="/signatures" component={Signatures} />
              <Route>
                <div className="text-center py-20">
                  <h2 className="text-2xl font-bold text-gray-600 mb-4">
                    עמוד לא נמצא
                  </h2>
                  <p className="text-gray-500">
                    העמוד שאתה מחפש לא קיים במערכת
                  </p>
                </div>
              </Route>
            </Switch>
          </Router>
        </main>
      </div>
    </div>
  );
}

export default App;