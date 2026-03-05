import { motion } from "framer-motion";
import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  delay?: number;
}

const GlassCard = ({ children, className = "", hover = false, delay = 0 }: GlassCardProps) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: "-50px" }}
    transition={{ duration: 0.5, delay }}
    whileHover={hover ? { y: -4, boxShadow: "0 12px 40px hsla(200, 80%, 55%, 0.12)" } : undefined}
    className={`glass-card-elevated p-6 ${className}`}
  >
    {children}
  </motion.div>
);

export default GlassCard;
