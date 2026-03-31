import TopBar from './TopBar'
import StatusStepper from './StatusStepper'
import ChatPanel from '../chat/ChatPanel'
import PreviewPanel from '../preview/PreviewPanel'
import FinalAnswerPopup from '../chat/FinalAnswerPopup'
import { useChatStore } from '../../stores/chatStore'

export default function AppShell() {
  const finalAnswerPopup = useChatStore((state) => state.finalAnswerPopup)
  const closeFinalAnswerPopup = useChatStore((state) => state.closeFinalAnswerPopup)

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <TopBar />
      <main className="flex-1 grid grid-cols-2 min-h-0">
        <div className="border-r border-gray-200 bg-white">
          <ChatPanel />
        </div>
        <div className="bg-gray-50">
          <PreviewPanel />
        </div>
      </main>
      <StatusStepper />
      <FinalAnswerPopup answer={finalAnswerPopup} onClose={closeFinalAnswerPopup} />
    </div>
  )
}
