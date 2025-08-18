'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Shield, Castle, Waves, Users, Database, TrendingUp, Lock, Zap, AlertTriangle } from 'lucide-react';

interface MoatData {
  company: string;
  moats: {
    type: string;
    strength: 'strong' | 'medium' | 'weak';
    description: string;
    icon?: React.ReactNode;
  }[];
  threats: {
    source: string;
    severity: 'high' | 'medium' | 'low';
    description: string;
  }[];
  supplierRelationships?: {
    supplier: string;
    dependency: 'critical' | 'important' | 'minor';
    isAlsoCompetitor: boolean;
  }[];
  marketPosition: {
    mainMarket: string;
    submarket: string;
    marketShare?: number;
    tam?: string;
    sam?: string;
  };
}

interface CompetitiveMoatCastleProps {
  data: MoatData;
}

const CompetitiveMoatCastle: React.FC<CompetitiveMoatCastleProps> = ({ data }) => {
  const getMoatColor = (strength: string) => {
    switch (strength) {
      case 'strong': return 'text-blue-600 bg-blue-50';
      case 'medium': return 'text-amber-600 bg-amber-50';
      case 'weak': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getThreatColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'text-red-600';
      case 'medium': return 'text-amber-600';
      case 'low': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  const getDefaultIcon = (type: string) => {
    const iconMap: { [key: string]: React.ReactNode } = {
      'data': <Database className="w-5 h-5" />,
      'network': <Users className="w-5 h-5" />,
      'technology': <Zap className="w-5 h-5" />,
      'brand': <Shield className="w-5 h-5" />,
      'scale': <TrendingUp className="w-5 h-5" />,
      'regulatory': <Lock className="w-5 h-5" />,
    };
    return iconMap[type.toLowerCase()] || <Shield className="w-5 h-5" />;
  };

  return (
    <div className="space-y-6">
      {/* Castle Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Castle className="w-6 h-6" />
            {data.company} - Competitive Moat Analysis
          </CardTitle>
          <CardDescription>
            {data.marketPosition.submarket} within {data.marketPosition.mainMarket}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative">
            {/* Castle SVG */}
            <svg viewBox="0 0 400 300" className="w-full h-auto">
              {/* Moat water */}
              <rect x="20" y="200" width="360" height="80" fill="#3b82f6" opacity="0.2" rx="10" />
              <text x="200" y="250" textAnchor="middle" className="fill-blue-600 text-xs font-medium">
                COMPETITIVE MOATS
              </text>
              
              {/* Castle base */}
              <rect x="100" y="120" width="200" height="80" fill="#6b7280" rx="5" />
              
              {/* Castle towers */}
              <rect x="80" y="80" width="40" height="120" fill="#6b7280" />
              <rect x="280" y="80" width="40" height="120" fill="#6b7280" />
              
              {/* Castle top */}
              <rect x="120" y="100" width="160" height="20" fill="#6b7280" />
              
              {/* Crenellations */}
              {[0, 1, 2, 3, 4, 5].map(i => (
                <rect key={i} x={130 + i * 25} y="90" width="15" height="10" fill="#6b7280" />
              ))}
              
              {/* Company name in castle */}
              <text x="200" y="150" textAnchor="middle" className="fill-white text-sm font-bold">
                {data.company}
              </text>
              <text x="200" y="170" textAnchor="middle" className="fill-white text-xs">
                {data.marketPosition.marketShare ? `${data.marketPosition.marketShare}% Market Share` : data.marketPosition.submarket}
              </text>
              
              {/* Threat arrows */}
              {data.threats.slice(0, 3).map((threat, index) => (
                <g key={index}>
                  <line 
                    x1={50 + index * 100} 
                    y1="50" 
                    x2={150 + index * 50} 
                    y2="100" 
                    stroke="red" 
                    strokeWidth="2"
                    markerEnd="url(#arrowhead)"
                  />
                  <text x={50 + index * 100} y="40" className="fill-red-600 text-xs">
                    {threat.source}
                  </text>
                </g>
              ))}
              
              {/* Arrow marker definition */}
              <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="red" />
                </marker>
              </defs>
            </svg>
          </div>
          
          {/* Moat Details */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.moats.map((moat, index) => (
              <div key={index} className={`p-4 rounded-lg ${getMoatColor(moat.strength)}`}>
                <div className="flex items-center gap-2 mb-2">
                  {moat.icon || getDefaultIcon(moat.type)}
                  <h4 className="font-semibold capitalize">{moat.type} Moat</h4>
                </div>
                <p className="text-sm">{moat.description}</p>
                <div className="mt-2">
                  <span className="text-xs font-medium uppercase">Strength: {moat.strength}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Market Position */}
      <Card>
        <CardHeader>
          <CardTitle>Market Position</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">Main Market</p>
              <p className="font-semibold">{data.marketPosition.mainMarket}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Submarket</p>
              <p className="font-semibold">{data.marketPosition.submarket}</p>
            </div>
            {data.marketPosition.tam && (
              <div>
                <p className="text-sm text-gray-600">TAM</p>
                <p className="font-semibold">{data.marketPosition.tam}</p>
              </div>
            )}
            {data.marketPosition.sam && (
              <div>
                <p className="text-sm text-gray-600">SAM</p>
                <p className="font-semibold">{data.marketPosition.sam}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Supplier Relationships */}
      {data.supplierRelationships && data.supplierRelationships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Supplier-Competitor Dynamics</CardTitle>
            <CardDescription>
              Complex relationships where suppliers are also competitors
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.supplierRelationships.map((rel, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className={`px-2 py-1 rounded text-xs font-medium ${
                      rel.dependency === 'critical' ? 'bg-red-100 text-red-700' :
                      rel.dependency === 'important' ? 'bg-amber-100 text-amber-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {rel.dependency}
                    </div>
                    <div>
                      <p className="font-medium">{rel.supplier}</p>
                      {rel.isAlsoCompetitor && (
                        <p className="text-xs text-amber-600 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Also a competitor
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Threats */}
      <Card>
        <CardHeader>
          <CardTitle>Competitive Threats</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {data.threats.map((threat, index) => (
              <div key={index} className="flex items-start gap-3 p-3 border rounded-lg">
                <AlertTriangle className={`w-5 h-5 mt-0.5 ${getThreatColor(threat.severity)}`} />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-medium">{threat.source}</h4>
                    <span className={`text-xs font-medium uppercase ${getThreatColor(threat.severity)}`}>
                      {threat.severity} severity
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{threat.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CompetitiveMoatCastle;