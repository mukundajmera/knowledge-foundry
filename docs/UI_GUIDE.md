# UI User Guide: Complete Interface Walkthrough

## Overview

This guide shows you how the Knowledge Foundry UI looks and works locally at **http://localhost:3000** with all features and plugins enabled.

## Main Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [☰] ✦ Knowledge Foundry    [💬 Chat] [📚 Docs] [🌓] [⌨️] [❓] [👤] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    ✦ Knowledge Foundry                          │
│         Your enterprise AI knowledge assistant                  │
│                                                                 │
│  💡 What is our data retention policy?                          │
│  💡 Explain the security architecture                           │
│  💡 What compliance frameworks do we follow?                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ⚙️ Advanced ▼                                                  │
│  [📎] Ask a question… (Ctrl+Enter to send, / to focus)    [→]  │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Header Bar

### Left Side
- **☰ Menu** (mobile): Toggle sidebar on small screens
- **✦ Knowledge Foundry**: Logo and branding

### Right Side
- **💬 Chat / 📚 Docs**: Two-view toggle
  - **Chat**: Main conversational interface
  - **Docs**: Document management (upload, search, delete)
- **🌓 Theme Toggle**: Switch light/dark mode
- **⌨️ Keyboard Shortcuts**: Show shortcuts modal
- **❓ Help**: Help resources
- **👤 User Profile**: User menu

## 2. Welcome Screen (First Visit)

When you have no messages:

```
                    ✦ (Large icon)
          Knowledge Foundry
 Your enterprise AI knowledge assistant.
Ask questions about your documents and
     get cited, accurate answers.

💡 What is our data retention policy?
💡 Explain the security architecture  
💡 What compliance frameworks do we follow?
```

- **Suggestion Chips**: Click any to fill the input
- **Auto-updates**: Disappears after first message

## 3. Query Input Area

### Basic Input
```
┌────────────────────────────────────────────┐
│ Ask a question…                      [→]  │
│ (Ctrl+Enter to send, / to focus)          │
└────────────────────────────────────────────┘
```

**Features:**
- Auto-resizing: Grows up to 200px height
- **Enter**: New line
- **Ctrl/Cmd + Enter**: Send
- **/ key**: Focus input from anywhere
- **Send button**: Disabled when empty

### Advanced Options

Click **⚙️ Advanced ▼** to expand:

```
┌─ Advanced Options ──────────────────┐
│ Model: [Auto ▼]                     │
│   • Auto (complexity-based)         │
│   • Haiku (Fast)                    │
│   • Sonnet (Balanced)               │
│   • Opus (Best)                     │
│                                     │
│ Deep Search:        [○────]  OFF   │
│ Multi-hop:          [○────]  OFF   │
└─────────────────────────────────────┘
```

**Options:**
- **Model**: Force a specific tier (overrides auto-routing)
- **Deep Search**: Use multi-agent supervisor for research
- **Multi-hop**: Enable graph traversal

### File Upload

```
[📎 Attach]  [file1.pdf ✕]  [file2.txt ✕]
```

**Features:**
- Click **📎** to browse files
- **Drag & drop** files onto input box
- Shows file chips with name and remove button
- Supports: PDF, TXT, MD, DOCX

## 4. Message Display

### User Message
```
┌─────────────────────────────────────────┐
│ [U] You                    10:23 AM    │
│                                         │
│ What is the security architecture?     │
└─────────────────────────────────────────┘
```

### AI Response

```
┌─────────────────────────────────────────┐
│ [✦] Knowledge Foundry    10:23 Amsonnet │
│                                         │
│ Our security architecture uses a        │
│ defense-in-depth approach [1]:          │
│                                         │
│ 1. Input Sanitization                  │
│ 2. Output Filtering                    │
│ 3. Audit Trails                        │
│                                         │
│ [View implementation details]           │
│                                         │
│ ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯│
│ 📊 85% confidence  ⚡ 1.5s  💰 $0.0045 │
│                                         │
│ 🔍 Routing: Auto → Sonnet (score: 0.6) │
│                                         │
│ [👍] [👎] [📋 Copy] [🔄 Regenerate]    │
│ [📚 Sources (2) ▼]                     │
│                                         │
│ Follow-up questions:                    │
│ 💬 How is input sanitization done?     │
│ 💬 What audit logs are captured?       │
└─────────────────────────────────────────┘
```

**Features:**

#### 1. Model Badge
- Shows which tier was used: `haiku` / `sonnet` / `opus`
- Color-coded: Blue (Haiku), Green (Sonnet), Red (Opus)

#### 2. Citations (In-text)
- Click `[1]` to highlight corresponding source
- Hover for preview

#### 3. Metadata Bar
- **📊 Confidence**: % confidence score
  - High (>80%): Green
  - Medium (50-80%): Yellow
  - Low (<50%): Red with warning
- **⚡ Latency**: Response time in seconds
- **💰 Cost**: USD cost per query

#### 4. Routing Trace
- Expandable: Click to see routing decision details
- Shows complexity score and tier selection

#### 5. Low Confidence Warning
If confidence < 50%:
```
⚠️ Low confidence — please verify independently.
```

#### 6. Action Buttons
- **👍 / 👎**: Feedback (local state)
- **📋 Copy**: Copy response to clipboard
- **🔄 Regenerate**: Re-generate with same prompt

#### 7. Sources Panel
Click **📚 Sources (2) ▼** to expand:

```
┌─ Sources ───────────────────────────┐
│ [1] Security Architecture v2.1  92% │
│     "Defense-in-depth involves..."  │
│                                     │
│ [2] OWASP Guidelines            85% │
│     "Input sanitization should..."  │
└─────────────────────────────────────┘
```

Shows:
- Citation number
- Document title
- Relevance score %
- Excerpt snippet

#### 8. Follow-up Suggestions
AI-generated related questions as chips:
- Click to auto-send

### Streaming Indicator

While AI is responding:
```
Our security architecture uses a ●●●
```

3-dot typing animation appears at the end.

**Stop Button:**
```
[⬜ Stop generating]
```

## 5. Sidebar (Conversation History)

```
┌─ Conversations ──────────────────┐
│ [🔍] Search conversations...     │
│                                  │
│ [+ New conversation]             │
│                                  │
│ ▼ Today                          │
│   Security architecture   (3 msg)│
│   Data retention policy   (5 msg)│
│                                  │
│ ▼ Yesterday                      │
│   Compliance audit        (8 msg)│
│                                  │
│ ▼ Last 7 days                    │
│   ...                            │
└──────────────────────────────────┘
```

**Features:**
- **Search**: Filter conversations by content
- **New conversation**: Creates blank chat
- **Auto-grouping**: Today, Yesterday, Week, Month, Older
- **Message count**: Shows # messages in conversation
- **Click**: Switch to that conversation
- **Hover**: Shows delete (🗑️) button

## 6. Documents View

Click **📚 Docs** tab:

```
┌─ Document Manager ───────────────────────┐
│ [🔍] Search documents...     [+ Upload]  │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ 📄 security-policy.pdf     [View]  │  │
│ │ 2.4 MB • Uploaded 2h ago   [🗑️]    │  │
│ │ ───────────────────────────────────│  │
│ │ Indexed: ✓ Chunks: 45  Entities: 12│  │
│ └────────────────────────────────────┘  │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ 📄 compliance-guide.md     [View]  │  │
│ │ 128 KB • Uploaded 1d ago   [🗑️]    │  │
│ │ ───────────────────────────────────│  │
│ │ Indexed: ✓ Chunks: 23  Entities: 8 │  │
│ └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Features:**
- **Upload**: Drag & drop or click to browse
- **Search**: Filter by filename or content
- **View**: Preview document
- **Delete**: Remove from index
- **Status**: Shows if indexed + chunk/entity count

## 7. Keyboard Shortcuts

Press **?** or click **⌨️** button:

```
┌─ Keyboard Shortcuts ──────────────┐
│                                   │
│  /      Focus query input         │
│  ?      Show this dialog          │
│  n      New conversation          │
│  Ctrl+Enter   Send query          │
│  Esc    Close dialog/panel        │
│                                   │
│         [Close: Esc]              │
└───────────────────────────────────┘
```

## 8. Theme Toggle

Click **🌓** to switch:

### Light Mode
- White background
- Dark text
- Blue accents

### Dark Mode (Default)
- Dark gray background
- Light text
- Cyan/purple accents

Persists to `localStorage`.

## 9. Error Handling

### Rate Limit
```
┌─ ⚠️ Error ───────────────────────┐
│ Rate limit exceeded              │
│ Try again in 42 seconds          │
│ [Retry in 42s...]                │
└──────────────────────────────────┘
```

### Network Error
```
┌─ ⚠️ Error ───────────────────────┐
│ Connection lost                  │
│ Check your internet connection   │
│ [Retry now]                      │
└──────────────────────────────────┘
```

### API Error
```
┌─ ⚠️ Error ───────────────────────┐
│ Server error (500)               │
│ Our team has been notified       │
│ [Try again]                      │
└──────────────────────────────────┘
```

Auto-retry with exponential backoff for transient errors.

## 10. Plugin Integration

While plugins run in the backend, the UI shows their effects:

### Web Search Plugin
```
🔍 Searching the web...
Found 5 recent articles about quantum computing
```
Results appear as citations.

### Code Sandbox Plugin
```
💻 Running code in sandbox...
✓ Execution completed (234ms)
```
Output appears inline in response.

### Database Plugin
```
🗄️ Querying knowledge base...
Found 12 relevant documents
```
Results feed into RAG context.

### Communication Plugin
```
📧 Sending summary via email...
✓ Sent to team@example.com
```
Confirmation shown in response.

## 11. Responsive Design

### Desktop (> 1024px)
- Sidebar always visible (left)
- Full chat area (center)
- Wide advanced options

### Tablet (768px - 1024px)
- Collapsible sidebar
- Adjusted spacing

### Mobile (< 768px)
- Sidebar as drawer (slide-in)
- Hamburger menu (☰)
- Stacked layout
- Touch-optimized buttons

## Accessibility

**WCAG AA Compliant:**
- ✅ Keyboard navigation
- ✅ Screen reader support
- ✅ ARIA labels
- ✅ Focus indicators
- ✅ Color contrast (>4.5:1)
- ✅ Semantic HTML

## Performance

**Optimizations:**
- Lazy loading of message history
- Virtualized conversation list (100+)
- Debounced search (300ms)
- Code splitting
- Image optimization

**Metrics:**
- First Contentful Paint: < 1s
- Time to Interactive: < 2s
- Lighthouse Score: 95+

## Browser Support

- Chrome/Edge: ✅ Latest 2 versions
- Firefox: ✅ Latest 2 versions
- Safari: ✅ Latest 2 versions
- Mobile Safari/Chrome: ✅ iOS 14+, Android 10+

## See Also

- [UI Automation Testing](UI_AUTOMATION_TESTING.md)
- [User Guide](USER_GUIDE.md)
- [API Documentation](API.md)
