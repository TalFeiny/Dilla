"use client"

import { ReactNode } from "react"

interface PageTransitionProps {
  children: ReactNode
  mode?: "wait" | "sync"
}

export function PageTransition({ children }: PageTransitionProps) {
  return <div>{children}</div>
}
