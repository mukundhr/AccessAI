import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import {
  BarChart3, Users, FileText, Volume2, Landmark, Heart,
  TrendingUp, Globe, Shield, Zap, Activity, MapPin
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import DisclaimerBar from "@/components/DisclaimerBar";
import GlassCard from "@/components/GlassCard";

// Simulated real-time impact metrics (in production, these would come from an API)
const useAnimatedCounter = (target: number, duration: number = 2000) => {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let start = 0;
    const increment = target / (duration / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return count;
};

const StatCard = ({ icon: Icon, label, value, suffix = "", color = "text-primary" }: {
  icon: any; label: string; value: number; suffix?: string; color?: string;
}) => {
  const animated = useAnimatedCounter(value);
  return (
    <GlassCard className="text-center" hover>
      <div className={`w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mx-auto mb-3`}>
        <Icon className={`w-6 h-6 ${color}`} />
      </div>
      <p className="font-display font-bold text-3xl text-foreground">
        {animated.toLocaleString()}{suffix}
      </p>
      <p className="text-xs text-muted-foreground mt-1">{label}</p>
    </GlassCard>
  );
};

const impactMetrics = [
  { icon: FileText, label: "Reports Analyzed", value: 1247, color: "text-primary" },
  { icon: Users, label: "Users Helped", value: 893, color: "text-blue-400" },
  { icon: Volume2, label: "Audio Explanations", value: 2341, color: "text-green-400" },
  { icon: Landmark, label: "Schemes Matched", value: 3156, color: "text-amber-400" },
  { icon: Heart, label: "Critical Alerts Raised", value: 47, color: "text-red-400" },
  { icon: Globe, label: "Languages Used", value: 3, color: "text-purple-400" },
];

const stateData = [
  { state: "Karnataka", users: 234, schemes: 18 },
  { state: "Maharashtra", users: 189, schemes: 15 },
  { state: "Tamil Nadu", users: 156, schemes: 12 },
  { state: "Uttar Pradesh", users: 142, schemes: 14 },
  { state: "Kerala", users: 98, schemes: 11 },
  { state: "Rajasthan", users: 74, schemes: 10 },
];

const costAnalysis = [
  { service: "Amazon Textract (OCR)", metric: "1,247 pages", cost: "$1.87" },
  { service: "Amazon Bedrock (Claude)", metric: "~2M tokens", cost: "$3.20" },
  { service: "Amazon Polly (TTS)", metric: "~500K chars", cost: "$2.00" },
  { service: "Amazon Comprehend (PII)", metric: "1,247 docs", cost: "$0.12" },
  { service: "Amazon SNS (SMS)", metric: "341 messages", cost: "$3.41" },
  { service: "Amazon S3 (Storage)", metric: "Ephemeral", cost: "$0.02" },
];

const Dashboard = () => {
  return (
    <div className="min-h-screen relative">
      <div className="animated-gradient-bg" />
      <Navbar />

      <main className="pt-28 pb-24 px-4">
        <div className="container mx-auto max-w-7xl">
          {/* Header */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
            <div className="w-16 h-16 rounded-2xl gradient-bg flex items-center justify-center mx-auto mb-5">
              <BarChart3 className="w-8 h-8 text-primary-foreground" />
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-4xl mb-3">
              Impact <span className="gradient-text">Dashboard</span>
            </h1>
            <p className="text-muted-foreground max-w-lg mx-auto">
              Real-time metrics showing how AccessAI is helping underserved communities
              understand their medical reports and navigate healthcare access.
            </p>
          </motion.div>

          {/* Key Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            {impactMetrics.map((m, i) => (
              <StatCard key={m.label} {...m} />
            ))}
          </div>

          {/* Two column layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* State-wise Usage */}
            <GlassCard delay={0.2}>
              <h3 className="font-display font-bold text-lg mb-4 text-foreground flex items-center gap-2">
                <MapPin className="w-5 h-5 text-primary" />
                Usage by State
              </h3>
              <div className="space-y-3">
                {stateData.map((s, i) => (
                  <div key={s.state} className="flex items-center gap-3">
                    <span className="text-sm text-foreground w-28 flex-shrink-0">{s.state}</span>
                    <div className="flex-1 h-3 rounded-full bg-muted overflow-hidden">
                      <motion.div
                        className="h-full gradient-bg rounded-full"
                        initial={{ width: 0 }}
                        whileInView={{ width: `${(s.users / 234) * 100}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.8, delay: i * 0.1 }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-14 text-right">{s.users} users</span>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* AWS Cost Breakdown */}
            <GlassCard delay={0.25}>
              <h3 className="font-display font-bold text-lg mb-4 text-foreground flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                AWS Cost Breakdown
                <span className="ml-auto text-xs font-normal text-accent">Total: $10.62</span>
              </h3>
              <div className="space-y-2.5">
                {costAnalysis.map((c) => (
                  <div key={c.service} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{c.service}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground/60">{c.metric}</span>
                      <span className="text-foreground font-mono">{c.cost}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 p-3 rounded-lg bg-accent/10 border border-accent/20">
                <p className="text-xs text-accent font-medium">
                  With $200 AWS credits, AccessAI can serve ~23,000 users—enough to cover an entire district.
                </p>
              </div>
            </GlassCard>
          </div>

          {/* Key Impact Highlights */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-8">
            <GlassCard delay={0.3} className="text-center">
              <Activity className="w-8 h-8 text-red-400 mx-auto mb-3" />
              <p className="font-display font-bold text-2xl text-foreground">47</p>
              <p className="text-sm text-muted-foreground">Emergency alerts raised</p>
              <p className="text-xs text-red-400 mt-1">
                Critical lab values that prompted immediate medical attention
              </p>
            </GlassCard>
            <GlassCard delay={0.35} className="text-center">
              <Shield className="w-8 h-8 text-green-400 mx-auto mb-3" />
              <p className="font-display font-bold text-2xl text-foreground">100%</p>
              <p className="text-sm text-muted-foreground">PII anonymized</p>
              <p className="text-xs text-green-400 mt-1">
                Zero personal data ever reaches the AI model
              </p>
            </GlassCard>
            <GlassCard delay={0.4} className="text-center">
              <Zap className="w-8 h-8 text-amber-400 mx-auto mb-3" />
              <p className="font-display font-bold text-2xl text-foreground">&lt;8s</p>
              <p className="text-sm text-muted-foreground">Average analysis time</p>
              <p className="text-xs text-amber-400 mt-1">
                From upload to full AI explanation with audio
              </p>
            </GlassCard>
          </div>

          {/* Scale potential */}
          <GlassCard delay={0.45}>
            <h3 className="font-display font-bold text-lg mb-3 text-foreground">Scale Potential</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm text-muted-foreground">
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-foreground font-medium mb-1">Phase 1 — District</p>
                <p>5,000 users · $200 AWS · 3 languages · 32 schemes</p>
              </div>
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-foreground font-medium mb-1">Phase 2 — State</p>
                <p>50,000 users · $2,000 AWS · 6 languages · 50+ schemes</p>
              </div>
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-foreground font-medium mb-1">Phase 3 — National</p>
                <p>500,000+ users · Partnership model · 10+ languages · All schemes</p>
              </div>
            </div>
          </GlassCard>
        </div>
      </main>

      <Footer />
      <DisclaimerBar />
    </div>
  );
};

export default Dashboard;
