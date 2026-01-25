import { GoogleGenAI } from '@google/genai';
import { getMockResponse } from './mockService';

export const generateGeminiResponse = async (prompt) => {
  const apiKey = process.env.API_KEY;
  
  // If no API key is provided, return mock response
  if (!apiKey || apiKey.trim() === "") {
    console.warn("No Gemini API key provided in process.env.API_KEY. Using mock response.");
    return getMockResponse(prompt);
  }
  
  try {
    const ai = new GoogleGenAI({ apiKey });
    
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash-preview-09-2025', 
      contents: prompt,
    });
    
    return response.text || "AI 响应为空";
  } catch (error) {
    console.error("Gemini API Error:", error);
    // Fallback to mock response on error
    return getMockResponse(prompt);
  }
};
