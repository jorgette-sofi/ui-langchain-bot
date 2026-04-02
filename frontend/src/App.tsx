import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Chat from './Chat';
import Admin from './Admin';

function App() {
  return (
    <Router>
      <Routes>
        {/* The main chat interface lives at the root URL */}
        <Route path="/" element={<Chat />} />
        {/* The admin dashboard lives at /admin */}
        <Route path="/admin" element={<Admin />} />
      </Routes>
    </Router>
  );
}

export default App;