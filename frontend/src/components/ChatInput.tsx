import React, { useState } from "react";

interface ChatInputProps {
  onSend: (text: string, fileText?: string) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, disabled }) => {
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileText, setFileText] = useState<string | undefined>(undefined);

  const handleSend = () => {
    if (!text.trim() && !fileText) return;
    onSend(text, fileText);
    setText("");
    setFileText(undefined);
    setFileName(null);
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled) {
        handleSend();
      }
    }
  };

  const handleFileChange: React.ChangeEventHandler<HTMLInputElement> = async e => {
    const file = e.target.files?.[0];
    if (!file) {
      setFileName(null);
      setFileText(undefined);
      return;
    }
    setFileName(file.name);
    const text = await file.text();
    setFileText(text);
  };

  return (
    <div className="chat-input-root">
      <div className="chat-input-main">
        <textarea
          className="chat-textarea"
          placeholder="Describe your scenario or paste test cases (URLs can be embedded in the text)..."
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
      </div>
      <div className="chat-input-footer">
        <div className="chat-input-left">
          <label className="file-upload">
            <span className="file-upload-label">
              {fileName ? `Attached: ${fileName}` : "Attach test case file"}
            </span>
            <input
              type="file"
              accept=".txt,.md,.json,.csv"
              onChange={handleFileChange}
            />
          </label>
        </div>
        <div className="chat-input-right">
          <button
            className="send-button"
            onClick={handleSend}
            disabled={disabled || (!text.trim() && !fileText)}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

