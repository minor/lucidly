import React from 'react';

interface SimpleMarkdownProps {
  content: string;
  className?: string;
}

export function SimpleMarkdown({ content, className = "" }: SimpleMarkdownProps) {
  if (!content) return null;

  // specialized simple parser for challenge descriptions
  const renderContent = (text: string) => {
    // Split by newlines to handle blocks
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let key = 0;
    
    let inCodeBlock = false;
    let codeBlockContent: string[] = [];
    let codeBlockLang = "";

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Code block handling
        if (line.trim().startsWith('```')) {
            if (inCodeBlock) {
                // End of code block
                elements.push(
                    <pre key={key++} className="bg-muted p-3 dashed rounded-md my-4 overflow-x-auto text-sm font-mono text-foreground">
                        <code>{codeBlockContent.join('\n')}</code>
                    </pre>
                );
                inCodeBlock = false;
                codeBlockContent = [];
                codeBlockLang = "";
            } else {
                // Start of code block
                inCodeBlock = true;
                codeBlockLang = line.replace('```', '').trim();
            }
            continue;
        }

        if (inCodeBlock) {
            codeBlockContent.push(line);
            continue;
        }

        // Headers
        if (line.startsWith('# ')) {
            elements.push(<h1 key={key++} className="text-2xl font-bold mt-6 mb-4">{parseInline(line.substring(2))}</h1>);
        } else if (line.startsWith('## ')) {
            elements.push(<h2 key={key++} className="text-xl font-bold mt-5 mb-3">{parseInline(line.substring(3))}</h2>);
        } else if (line.startsWith('### ')) {
            elements.push(<h3 key={key++} className="text-lg font-semibold mt-4 mb-2">{parseInline(line.substring(4))}</h3>);
        } else if (line.startsWith('- ')) {
            // List item (simple assumption: consecutive list items are part of same list, 
            // but for simplicity we'll render as div with bullet)
            elements.push(
                <div key={key++} className="flex gap-2 ml-4 my-1">
                    <span>•</span>
                    <div>{parseInline(line.substring(2))}</div>
                </div>
            );
        } else if (line.trim() === '') {
            elements.push(<div key={key++} className="h-4" />); // Spacer
        } else {
            // Paragraph
            elements.push(<p key={key++} className="my-2 leading-relaxed">{parseInline(line)}</p>);
        }
    }
    
    return elements;
  };

  // Helper for inline styles (bold, code)
  const parseInline = (text: string): React.ReactNode => {
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
    return parts.map((part, index) => {
        if (part.startsWith('`') && part.endsWith('`')) {
            return <code key={index} className="bg-muted px-1 py-0.5 rounded font-mono text-sm">{part.slice(1, -1)}</code>;
        }
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={index} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        return part;
    });
  };

  return <div className={`text-foreground/90 ${className}`}>{renderContent(content)}</div>;
}
