import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  FileUp, Brain, MessageSquareText, Volume2, Landmark, Wifi,
  ShieldCheck, Languages, Zap
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import DisclaimerBar from "@/components/DisclaimerBar";
import GlassCard from "@/components/GlassCard";
import VoicePulse from "@/components/VoicePulse";
import { useI18n } from "@/lib/i18n";

const featureKeys = [
  { icon: FileUp, titleKey: "features.upload.title", descKey: "features.upload.desc", color: "text-white-300" },
  { icon: Brain, titleKey: "features.ai.title", descKey: "features.ai.desc", color: "text-orange-400" },
  { icon: MessageSquareText, titleKey: "features.questions.title", descKey: "features.questions.desc", color: "text-white-200" },
  { icon: Volume2, titleKey: "features.audio.title", descKey: "features.audio.desc", color: "text-green-400" },
  { icon: Landmark, titleKey: "features.schemes.title", descKey: "features.schemes.desc", color: "text-orange-300" },
  { icon: Wifi, titleKey: "features.bandwidth.title", descKey: "features.bandwidth.desc", color: "text-white-400" },
];

const whyKeys = [
  { icon: ShieldCheck, titleKey: "why.reduces.title", descKey: "why.reduces.desc", color: "text-green-400" },
  { icon: Languages, titleKey: "why.language.title", descKey: "why.language.desc", color: "text-white-300" },
  { icon: Zap, titleKey: "why.speed.title", descKey: "why.speed.desc", color: "text-orange-400" },
];

const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.1 } } };
const fadeUp = { hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

const Index = () => {
  const { t } = useI18n();

  return (
    <div className="min-h-screen relative">
      <div className="animated-gradient-bg" />
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-20 sm:pt-36 sm:pb-28 px-4">
        <div className="container mx-auto flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6 }}
            className="mb-8"
          >
            <VoicePulse size={80} />
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="font-display font-bold text-3xl sm:text-5xl lg:text-6xl leading-tight max-w-3xl mb-5"
          >
            {t("hero.title1")}{" "}
            <span className="gradient-text">{t("hero.title2")}</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="text-lg sm:text-xl text-muted-foreground max-w-xl mb-10"
          >
            {t("hero.subtitle")}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.55 }}
          >
            <Link
              to="/upload"
              className="btn-primary-gradient inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold"
            >
              {t("nav.startNow")}
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 px-4">
        <div className="container mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="font-display text-2xl sm:text-3xl font-bold text-center mb-12"
          >
            {t("features.heading")}
          </motion.h2>

          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-80px" }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
          >
            {featureKeys.map((f) => (
              <motion.div key={f.titleKey} variants={fadeUp}>
                <GlassCard hover delay={0} className="h-full">
                  <div className="w-11 h-11 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                    <f.icon className={`w-5 h-5 ${f.color}`} />
                  </div>
                  <h3 className="font-display font-semibold text-lg mb-2 text-foreground">{t(f.titleKey)}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{t(f.descKey)}</p>
                </GlassCard>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Why AccessAI */}
      <section className="py-16 px-4">
        <div className="container mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="font-display text-2xl sm:text-3xl font-bold text-center mb-12"
          >
            {t("why.heading")} <span className="gradient-text">AccessAI</span>?
          </motion.h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {whyKeys.map((item, i) => (
              <GlassCard key={item.titleKey} delay={i * 0.15} className="text-center">
                <div className="w-14 h-14 rounded-2xl gradient-bg-subtle flex items-center justify-center mx-auto mb-5">
                  <item.icon className={`w-7 h-7 ${item.color}`} />
                </div>
                <h3 className="font-display font-semibold text-lg mb-3 text-foreground">{t(item.titleKey)}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{t(item.descKey)}</p>
              </GlassCard>
            ))}
          </div>
        </div>
      </section>

      <Footer />
      <DisclaimerBar />
    </div>
  );
};

export default Index;
