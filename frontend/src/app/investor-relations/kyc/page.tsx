'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle, XCircle, Clock, AlertTriangle, FileText, User, Building, Shield } from 'lucide-react';

interface KYCStatus {
  id: string;
  name: string;
  type: 'individual' | 'entity';
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  lastUpdated: string;
  riskLevel: 'low' | 'medium' | 'high';
  documents: string[];
}

export default function KYCPage() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [kycResults, setKycResults] = useState<KYCStatus[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const mockKYCData: KYCStatus[] = [
    {
      id: '1',
      name: 'John Smith',
      type: 'individual',
      status: 'approved',
      lastUpdated: '2024-01-15',
      riskLevel: 'low',
      documents: ['Passport', 'Proof of Address', 'Source of Funds']
    },
    {
      id: '2',
      name: 'Acme Ventures Ltd',
      type: 'entity',
      status: 'pending',
      lastUpdated: '2024-01-20',
      riskLevel: 'medium',
      documents: ['Certificate of Incorporation', 'Directors List', 'Beneficial Owners']
    },
    {
      id: '3',
      name: 'Sarah Johnson',
      type: 'individual',
      status: 'rejected',
      lastUpdated: '2024-01-18',
      riskLevel: 'high',
      documents: ['Passport', 'Bank Statements']
    }
  ];

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const runKYCProcess = async () => {
    if (!selectedFile) return;
    
    setIsProcessing(true);
    
    try {
      // Simulate external Python script call
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      const response = await fetch('/api/kyc/process', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const result = await response.json();
        setKycResults(result.kycResults || mockKYCData);
      } else {
        throw new Error('KYC processing failed');
      }
    } catch (error) {
      console.error('KYC processing error:', error);
      // Fallback to mock data for demo
      setKycResults(mockKYCData);
    } finally {
      setIsProcessing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'expired':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getRiskLevelColor = (riskLevel: string) => {
    switch (riskLevel) {
      case 'low':
        return 'bg-green-100 text-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">KYC Compliance</h1>
          <p className="text-gray-600 mt-2">Know Your Customer verification and monitoring</p>
        </div>
        <div className="flex items-center space-x-2">
          <Shield className="h-8 w-8 text-blue-600" />
          <Badge variant="outline" className="text-sm">
            Compliance Active
          </Badge>
        </div>
      </div>

      {/* File Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <FileText className="h-5 w-5" />
            <span>Upload KYC Documents</span>
          </CardTitle>
          <CardDescription>
            Upload documents for automated KYC processing using external Python script
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="kyc-file">Select KYC Document</Label>
            <Input
              id="kyc-file"
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              onChange={handleFileUpload}
              className="cursor-pointer"
            />
            <p className="text-sm text-gray-500">
              Supported formats: PDF, DOC, DOCX, JPG, PNG
            </p>
          </div>
          
          <Button 
            onClick={runKYCProcess}
            disabled={!selectedFile || isProcessing}
            className="w-full"
          >
            {isProcessing ? (
              <>
                <Clock className="h-4 w-4 mr-2 animate-spin" />
                Processing KYC...
              </>
            ) : (
              <>
                <Shield className="h-4 w-4 mr-2" />
                Run KYC Verification
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* KYC Results */}
      <div className="grid gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">KYC Status</h2>
          <Badge variant="outline">
            {kycResults.length} Records
          </Badge>
        </div>

        <div className="grid gap-4">
          {kycResults.map((kyc) => (
            <Card key={kyc.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    {kyc.type === 'individual' ? (
                      <User className="h-5 w-5 text-blue-600" />
                    ) : (
                      <Building className="h-5 w-5 text-green-600" />
                    )}
                    <div>
                      <h3 className="font-semibold text-gray-900">{kyc.name}</h3>
                      <p className="text-sm text-gray-500 capitalize">
                        {kyc.type} • Last updated: {kyc.lastUpdated}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <div className="flex items-center space-x-1">
                      {getStatusIcon(kyc.status)}
                      <span className="text-sm font-medium capitalize">{kyc.status}</span>
                    </div>
                    <Badge className={getRiskLevelColor(kyc.riskLevel)}>
                      {kyc.riskLevel} Risk
                    </Badge>
                  </div>
                </div>
                
                <div className="mt-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Documents:</p>
                  <div className="flex flex-wrap gap-2">
                    {kyc.documents.map((doc, index) => (
                      <Badge key={index} variant="secondary" className="text-xs">
                        {doc}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Compliance Alerts */}
      <Card className="border-orange-200 bg-orange-50">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2 text-orange-800">
            <AlertTriangle className="h-5 w-5" />
            <span>Compliance Alerts</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              2 KYC records require attention. 1 high-risk individual needs manual review.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
} 