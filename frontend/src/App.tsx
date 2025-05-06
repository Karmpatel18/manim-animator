import { useState, useEffect } from 'react'
import './App.css'

interface Chat {
  id: string;
  description: string;
  videoUrl: string;
  timestamp: string;
}

function App() {
  const [description, setDescription] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [chats, setChats] = useState<Chat[]>([])
  const [currentVideo, setCurrentVideo] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) return

    setIsLoading(true)
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

      const response = await fetch('http://localhost:5000/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ description }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to generate animation' }));
        throw new Error(errorData.error || 'Failed to generate animation');
      }

      // Get the video blob
      const videoBlob = await response.blob();
      if (videoBlob.size === 0) {
        throw new Error('Received empty video file');
      }

      const videoUrl = URL.createObjectURL(videoBlob);
      
      const newChat: Chat = {
        id: Date.now().toString(),
        description,
        videoUrl,
        timestamp: new Date().toLocaleString()
      };

      setChats(prev => [newChat, ...prev]);
      setCurrentVideo(videoUrl);
      setDescription('');
    } catch (error) {
      console.error('Error:', error);
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          alert('Request timed out. The animation generation is taking too long.');
        } else {
          alert(error.message);
        }
      } else {
        alert('Failed to generate animation. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="border-b border-gray-200 p-4">
          <h1 className="text-xl font-semibold text-gray-800">Animation History</h1>
        </div>
        <div className="flex-1 overflow-y-auto">
          {chats.map((chat) => (
            <div
              key={chat.id}
              className="p-4 border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
              onClick={() => setCurrentVideo(chat.videoUrl)}
            >
              <p className="text-sm text-gray-600 truncate">{chat.description}</p>
              <p className="text-xs text-gray-400 mt-1">{chat.timestamp}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Video Display */}
        <div className="flex-1 p-6 bg-gray-100 flex items-center justify-center">
          {isLoading ? (
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
              <p className="mt-4 text-gray-600">Generating your animation...</p>
            </div>
          ) : currentVideo ? (
            <video
              src={currentVideo}
              controls
              className="max-w-full max-h-full rounded-lg shadow-lg"
            />
          ) : (
            <div className="text-center text-gray-500">
              <p>Enter a description to generate an animation</p>
            </div>
          )}
        </div>

        {/* Input Form */}
        <div className="p-4 bg-white border-t border-gray-200">
          <form onSubmit={handleSubmit} className="flex gap-4">
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe your animation..."
              className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            >
              Generate
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default App
