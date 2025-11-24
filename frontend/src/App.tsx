import Header from './components/Header';
import MapView from './components/MapView';

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-gray-100">
      <Header />
      <div className="flex-1 relative h-[calc(100vh-64px)]">
        <MapView />
      </div>
    </div>
  );
}

export default App;
