import { Outlet } from 'react-router-dom'
import { ChatSessionProvider } from './lib/chatSession'
import Sidebar from './components/Sidebar'

function App() {
  return (
    <ChatSessionProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </ChatSessionProvider>
  )
}

export default App
