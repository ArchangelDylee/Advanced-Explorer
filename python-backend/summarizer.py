"""
파일 내용 요약 엔진 (TextRank)
"""

import logging
from typing import Dict
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.nlp.stemmers import Stemmer
import nltk
import os

logger = logging.getLogger(__name__)

# NLTK 데이터 자동 다운로드
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    logger.info("NLTK punkt tokenizer 다운로드 중...")
    try:
        nltk.download('punkt', quiet=True)
        logger.info("✓ NLTK punkt tokenizer 다운로드 완료")
    except Exception as e:
        logger.warning(f"NLTK punkt 다운로드 실패: {e}")

class ContentSummarizer:
    """TextRank 기반 내용 요약"""
    
    def __init__(self):
        logger.info("✓ TextRank 요약 엔진 초기화")
    
    def summarize(self, text: str, sentences_count: int = 5) -> Dict:
        """
        TextRank 알고리즘으로 요약
        
        Args:
            text: 요약할 텍스트
            sentences_count: 요약 문장 수 (기본 5개)
        
        Returns:
            요약 결과 딕셔너리
        """
        try:
            if not text or len(text.strip()) < 100:
                return {
                    'success': False,
                    'error': '텍스트가 너무 짧습니다 (최소 100자 필요)',
                    'summary': None
                }
            
            # 언어 감지 (표시용)
            has_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])
            language = 'korean' if has_korean else 'english'
            
            # TextRank 요약 (모든 언어를 english 토크나이저로 처리)
            # TextRank는 문장 간 유사도 기반이므로 언어에 관계없이 작동
            parser = PlaintextParser.from_string(text, Tokenizer('english'))
            stemmer = Stemmer('english')
            summarizer = TextRankSummarizer(stemmer)
            
            # 요약 문장 추출 (문단별 구분을 위해 빈 줄 추가)
            summary_sentences = summarizer(parser.document, sentences_count)
            summary = '\n\n'.join([str(sentence) for sentence in summary_sentences])
            
            if not summary:
                return {
                    'success': False,
                    'error': '요약 생성 실패',
                    'summary': None
                }
            
            logger.info(f"✓ TextRank 요약 완료: {len(text)}자 → {len(summary)}자")
            
            return {
                'success': True,
                'method': 'TextRank',
                'summary': summary,
                'original_length': len(text),
                'summary_length': len(summary),
                'compression_ratio': f"{(len(summary) / len(text) * 100):.1f}%",
                'sentences_count': sentences_count,
                'language': language
            }
            
        except Exception as e:
            logger.error(f"TextRank 요약 오류: {e}")
            return {
                'success': False,
                'error': f'요약 오류: {str(e)}',
                'summary': None
            }
