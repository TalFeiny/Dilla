import swaggerJsdoc from 'swagger-jsdoc';

const options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'VC Document Processor API',
      version: '1.0.0',
      description: 'API for processing venture capital documents like pitch decks, financial statements, and term sheets',
      contact: {
        name: 'API Support',
        email: 'support@yourcompany.com'
      }
    },
    servers: [
      {
        url: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
        description: 'Development server'
      }
    ],
    components: {
      schemas: {
        DocumentMetadata: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            filename: { type: 'string' },
            file_type: { type: 'string' },
            file_size: { type: 'number' },
            upload_date: { type: 'string', format: 'date-time' },
            processed: { type: 'boolean' },
            document_type: { 
              type: 'string', 
              enum: ['pitch_deck', 'financial_statement', 'due_diligence', 'term_sheet', 'other'] 
            }
          }
        },
        ProcessingResult: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            documentId: { type: 'string' },
            pythonOutput: { type: 'object' },
            processedData: { type: 'object' },
            error: { type: 'string' }
          }
        },
        Document: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            filename: { type: 'string' },
            file_type: { type: 'string' },
            file_size: { type: 'string' },
            document_type: { type: 'string' },
            upload_date: { type: 'string', format: 'date-time' },
            processed: { type: 'boolean' },
            has_results: { type: 'boolean' },
            summary: { type: 'object' },
            links: {
              type: 'object',
              properties: {
                document: { type: 'string' },
                results: { type: 'string' },
                status: { type: 'string' }
              }
            }
          }
        },
        DocumentsResponse: {
          type: 'object',
          properties: {
            documents: {
              type: 'array',
              items: { $ref: '#/components/schemas/Document' }
            },
            pagination: {
              type: 'object',
              properties: {
                page: { type: 'integer' },
                limit: { type: 'integer' },
                total: { type: 'integer' }
              }
            },
            filters: {
              type: 'object',
              properties: {
                document_type: { type: 'string' },
                processed: { type: 'string' }
              }
            }
          }
        },
        Error: {
          type: 'object',
          properties: {
            error: { type: 'string' },
            details: { type: 'string' }
          }
        }
      }
    }
  },
  apis: ['./app/api/**/*.ts'], // Path to the API docs
};

export const specs = swaggerJsdoc(options); 