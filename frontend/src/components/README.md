# Reusable Components Guide

This guide explains how to create and use reusable components in the VC Platform.

## 🏗️ Component Structure

```
components/
├── ui/           # Basic UI components (Button, Icon, Input, etc.)
├── layout/       # Layout components (PageHeader, Sidebar, etc.)
├── cards/        # Card-based components (NavigationCard, etc.)
└── index.ts      # Central export file
```

## 📦 Creating Reusable Components

### 1. **Component Structure**
```tsx
import React, { ReactNode } from 'react'

interface ComponentProps {
  title: string
  description?: string
  children?: ReactNode
}

export default function ComponentName({ title, description, children }: ComponentProps) {
  return (
    <div className="component-styles">
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {children}
    </div>
  )
}
```

### 2. **TypeScript Interfaces**
- Always define proper TypeScript interfaces
- Use optional properties with `?`
- Extend HTML element props when needed
- Use union types for variants: `'primary | secondary'`

### 3. **Styling Patterns**
```tsx
// Color variants object
const variants = {
  primary:bg-blue-600 text-white hover:bg-blue-700,
  secondary:bg-gray-600 text-white hover:bg-gray-700',
}

// Size variants
const sizes = {
  sm: px-3y-1 text-sm,
  md: 'px-4 py-2 text-base,
  lg: px-6 py-3 text-lg',
}
```

## 🎯 Available Components

### **UI Components**
- `Button` - Reusable button with variants
- `Icon` - SVG icon component with predefined icons

### **Layout Components**
- `PageHeader` - Consistent page headers with title, description, and actions

### **Card Components**
- `NavigationCard` - Navigation cards with icons and hover effects

## 🔧 Using Components

### **Import from Index**
```tsx
import { Button, Icon, PageHeader, NavigationCard } from '@/components'
```

### **Direct Import**
```tsx
import Button from@/components/ui/Button
import Icon from@/components/ui/Icon'
```

## 📝 Best Practices

### **1. Props Design**
- Keep props simple and focused
- Use descriptive prop names
- Provide sensible defaults
- Use TypeScript for type safety

### **2yling**
- Use Tailwind CSS classes
- Create reusable style variants
- Follow the design system
- Use consistent spacing and colors

### **3. Accessibility**
- Include proper ARIA labels
- Use semantic HTML
- Ensure keyboard navigation
- Test with screen readers

### **4erformance**
- Use React.memo for expensive components
- Avoid inline styles
- Optimize re-renders
- Lazy load when appropriate

## 🎨 Creating New Components

### **Step 1: Create the Component File**
```tsx
// components/ui/NewComponent.tsx
import React, { ReactNode } from 'react'

interface NewComponentProps {
  title: string
  children?: ReactNode
}

export default function NewComponent({ title, children }: NewComponentProps) {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm">
      <h3 className="text-lg font-semibold mb-4">{title}</h3
      {children}
    </div>
  )
}
```

### **Step 2: Add to Index File**
```tsx
// components/index.ts
export { default as NewComponent } from ./ui/NewComponent
```

### **Step 3Use in Pages**
```tsx
import { NewComponent } from '@/components'

export default function MyPage() {
  return (
    <NewComponent title="My Title">
      <p>Content goes here</p>
    </NewComponent>
  )
}
```

## 🔄 Component Patterns

### **Compound Components**
```tsx
// components/ui/Card.tsx
interface CardProps {
  children: ReactNode
}

interface CardHeaderProps {
  title: string
}

interface CardBodyProps {
  children: ReactNode
}

export function Card({ children }: CardProps) {
  return <div className="card">{children}</div>
}

Card.Header = function CardHeader({ title }: CardHeaderProps) {
  return <div className="card-header">{title}</div>
}

Card.Body = function CardBody({ children }: CardBodyProps) {
  return <div className="card-body">{children}</div>
}
```

### **Render Props Pattern**
```tsx
import React, { useState, ReactNode } from 'react'

interface DataFetcherProps {
  url: string
  children: (data: any, loading: boolean) => ReactNode
}

export function DataFetcher({ url, children }: DataFetcherProps) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  
  // Fetch logic here
  
  return <>{children(data, loading)}</>
}
```

## 🧪 Testing Components

### **Unit Tests**
```tsx
import { render, screen } from '@testing-library/react'
import { Button } from '@/components'

test('renders button with correct text', () => {
  render(<Button>Click me</Button>)
  expect(screen.getByText('Click me')).toBeInTheDocument()
})
```

### **Storybook Stories**
```tsx
// Button.stories.tsx
import { Button } from '@/components'

export default {
  title: 'UI/Button',
  component: Button,
}

export const Primary = () => <Button variant="primary>Primary Button</Button>
export const Secondary = () => <Button variant="secondary>Secondary Button</Button>
```

## 📚 Resources

- [React Component Patterns](https://reactpatterns.com/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) 