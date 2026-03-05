import { motion } from "framer-motion";
import { Shield, Lock, Eye, Database, Trash2, Mail } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import GlassCard from "@/components/GlassCard";
import { useI18n } from "@/lib/i18n";

const Privacy = () => {
  const { t } = useI18n();
  const sections = [
    {
      icon: Shield,
      titleKey: "privacy.section1.title",
      contentKey: "privacy.section1.content",
    },
    {
      icon: Lock,
      titleKey: "privacy.section2.title",
      contentKey: "privacy.section2.content",
    },
    {
      icon: Eye,
      titleKey: "privacy.section3.title",
      contentKey: "privacy.section3.content",
    },
    {
      icon: Database,
      titleKey: "privacy.section4.title",
      contentKey: "privacy.section4.content",
    },
    {
      icon: Trash2,
      titleKey: "privacy.section5.title",
      contentKey: "privacy.section5.content",
    },
    {
      icon: Mail,
      titleKey: "privacy.section6.title",
      contentKey: "privacy.section6.content",
    },
  ];

  return (
    <div className="min-h-screen relative">
      <div className="animated-gradient-bg" />
      <Navbar />

      {/* Hero Section */}
      <section className="pt-28 pb-16 px-4">
        <div className="container mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center max-w-3xl mx-auto"
          >
            <div className="w-20 h-20 rounded-2xl gradient-bg flex items-center justify-center mx-auto mb-6">
              <Shield className="w-10 h-10 text-primary-foreground" />
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-5xl lg:text-6xl leading-tight mb-6">
              {t("privacy.title")}
            </h1>
            <p className="text-lg sm:text-xl text-muted-foreground leading-relaxed">
              {t("privacy.subtitle")}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Last Updated */}
      <section className="py-8 px-4">
        <div className="container mx-auto text-center">
          <p className="text-muted-foreground">
            <span className="font-semibold text-foreground">
              {t("privacy.lastUpdated")}
            </span>{" "}
            {t("privacy.lastUpdatedDate")}
          </p>
        </div>
      </section>

      {/* Privacy Sections */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          {sections.map((section, i) => (
            <motion.div
              key={section.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="mb-8"
            >
              <GlassCard className="p-6 sm:p-8">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center flex-shrink-0">
                    <section.icon className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h2 className="font-display text-xl font-semibold mb-3">
                      {t(section.titleKey)}
                    </h2>
                    <p className="text-muted-foreground leading-relaxed">
                      {t(section.contentKey)}
                    </p>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Data Sharing */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-6 sm:p-8">
              <h2 className="font-display text-xl font-semibold mb-4">
                {t("privacy.dataSharing.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                {t("privacy.dataSharing.content1")}
                <span className="font-semibold text-foreground">
                  {t("privacy.dataSharing.not")}
                </span>
                {t("privacy.dataSharing.content2")}
              </p>
              <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-2">
                <li>{t("privacy.dataSharing.list1")}</li>
                <li>{t("privacy.dataSharing.list2")}</li>
                <li>{t("privacy.dataSharing.list3")}</li>
                <li>{t("privacy.dataSharing.list4")}</li>
              </ul>
              <p className="text-muted-foreground leading-relaxed mt-4">
                {t("privacy.dataSharing.content3")}
              </p>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* Compliance */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-6 sm:p-8">
              <h2 className="font-display text-xl font-semibold mb-4">
                {t("privacy.compliance.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                {t("privacy.compliance.content1")}
              </p>
              <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-2">
                <li>{t("privacy.compliance.list1")}</li>
                <li>{t("privacy.compliance.list2")}</li>
                <li>{t("privacy.compliance.list3")}</li>
              </ul>
              <p className="text-muted-foreground leading-relaxed mt-4">
                {t("privacy.compliance.content2")}
              </p>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Privacy;
