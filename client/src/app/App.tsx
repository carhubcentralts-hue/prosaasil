import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../features/auth/hooks';
import { AppRoutes } from './routes';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;