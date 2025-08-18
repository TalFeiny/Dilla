import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import fs from 'fs';
import path from 'path';

if (!supabaseService) {
  throw new Error('Supabase service not configured');
}

export async function GET(request: NextRequest) {
  try {
    const filePath = '1753193402747/Equitee.pdf';
    
    console.log('Testing download of:', filePath);
    
    const { data: fileData, error: downloadError } = await supabaseService.storage
      .from('documents')
      .download(filePath);

    if (downloadError || !fileData) {
      console.error('Download failed:', downloadError);
      return NextResponse.json({ error: 'Download failed', details: downloadError });
    }

    console.log('Download successful, file size:', fileData.size);
    
    // Save file locally
    const uploadsDir = path.join(process.cwd(), 'uploads');
    if (!fs.existsSync(uploadsDir)) {
      fs.mkdirSync(uploadsDir, { recursive: true });
    }

    const localFilePath = path.join(uploadsDir, 'test-download.pdf');
    
    const arrayBuffer = await fileData.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    fs.writeFileSync(localFilePath, buffer);
    
    console.log('File saved to:', localFilePath);
    
    return NextResponse.json({ 
      success: true, 
      message: 'Download and save successful',
      fileSize: fileData.size,
      localPath: localFilePath
    });
    
  } catch (error) {
    console.error('Test download error:', error);
    return NextResponse.json({ error: 'Test failed', details: error });
  }
} 