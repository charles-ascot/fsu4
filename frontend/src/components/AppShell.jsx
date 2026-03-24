import Sidebar from './Sidebar'

export default function AppShell({ children }) {
  return (
    <div className="relative z-10 flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        {children}
      </main>
    </div>
  )
}
