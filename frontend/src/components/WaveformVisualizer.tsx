import { motion } from "framer-motion";

const WaveformVisualizer = ({ playing = false }: { playing?: boolean }) => {
  const bars = 12;
  return (
    <div className="flex items-center gap-[3px] h-8">
      {Array.from({ length: bars }).map((_, i) => (
        <motion.div
          key={i}
          className="w-1 rounded-full"
          style={{
            background: `linear-gradient(to top, hsl(200, 80%, 55%), hsl(172, 60%, 45%))`,
          }}
          animate={
            playing
              ? { height: [6, 14 + Math.random() * 16, 6] }
              : { height: 6 }
          }
          transition={{
            duration: 0.6 + Math.random() * 0.4,
            repeat: playing ? Infinity : 0,
            ease: "easeInOut",
            delay: i * 0.06,
          }}
        />
      ))}
    </div>
  );
};

export default WaveformVisualizer;
