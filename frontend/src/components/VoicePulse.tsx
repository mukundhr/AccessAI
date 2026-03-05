import { motion } from "framer-motion";
import { Mic } from "lucide-react";

const VoicePulse = ({ size = 64 }: { size?: number }) => (
  <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
    <motion.div
      className="absolute inset-0 rounded-full gradient-bg opacity-20"
      animate={{ scale: [1, 1.6, 1], opacity: [0.3, 0, 0.3] }}
      transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
    />
    <motion.div
      className="absolute inset-1 rounded-full gradient-bg opacity-30"
      animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.1, 0.4] }}
      transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
    />
    <div
      className="relative rounded-full gradient-bg flex items-center justify-center"
      style={{ width: size * 0.55, height: size * 0.55 }}
    >
      <Mic className="text-primary-foreground" style={{ width: size * 0.28, height: size * 0.28 }} />
    </div>
  </div>
);

export default VoicePulse;
