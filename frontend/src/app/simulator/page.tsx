'use client';

import React from 'react';
import PortfolioSimulator from '@/components/portfolio/PortfolioSimulator';
import DataRoomManager from '@/components/data-room/DataRoomManager';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Brain, Briefcase, LineChart, Globe } from 'lucide-react';

export default function SimulatorPage() {
  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <LineChart className="h-8 w-8 text-primary" />
          Portfolio Simulator & Data Room
        </h1>
        <p className="text-muted-foreground mt-2">
          Turn £300 into £100K+ with concentrated alpha generation
        </p>
      </div>

      <Tabs defaultValue="simulator" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="simulator" className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            Portfolio Simulator
          </TabsTrigger>
          <TabsTrigger value="dataroom" className="flex items-center gap-2">
            <Briefcase className="h-4 w-4" />
            Data Room
          </TabsTrigger>
        </TabsList>

        <TabsContent value="simulator" className="mt-6">
          <PortfolioSimulator />
        </TabsContent>

        <TabsContent value="dataroom" className="mt-6">
          <DataRoomManager />
        </TabsContent>
      </Tabs>
    </div>
  );
}