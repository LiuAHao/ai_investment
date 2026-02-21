import React, { useState, useEffect, useRef } from 'react';

/**
 * 打字机效果文本组件
 * 逐字显示文本，模拟打字机效果
 */
export default function TypewriterText({ text, speed = 20, className = '', onComplete }) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const prevTextRef = useRef('');
  const timerRef = useRef(null);

  useEffect(() => {
    // 如果文本没有变化，不重新执行动画
    if (text === prevTextRef.current) return;
    prevTextRef.current = text;

    if (!text) {
      setDisplayedText('');
      setIsComplete(true);
      return;
    }

    // 清除之前的定时器
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    setDisplayedText('');
    setIsComplete(false);
    let index = 0;

    timerRef.current = setInterval(() => {
      if (index < text.length) {
        setDisplayedText(text.substring(0, index + 1));
        index++;
      } else {
        clearInterval(timerRef.current);
        timerRef.current = null;
        setIsComplete(true);
        onComplete?.();
      }
    }, speed);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [text, speed]);

  return (
    <span className={className}>
      {displayedText}
      {!isComplete && (
        <span className="inline-block w-0.5 h-4 bg-slate-400 ml-0.5 animate-pulse align-middle" />
      )}
    </span>
  );
}
