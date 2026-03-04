import { motion } from "framer-motion";
import { AlertTriangle, Stethoscope, Clock, FileText, CheckCircle } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import GlassCard from "@/components/GlassCard";
import { useI18n } from "@/lib/i18n";

const Disclaimer = () => {
  const { t } = useI18n();
  const importantNotices = [
    {
      icon: Stethoscope,
      titleKey: "disclaimer.notice1.title",
      contentKey: "disclaimer.notice1.content",
    },
    {
      icon: AlertTriangle,
      titleKey: "disclaimer.notice2.title",
      contentKey: "disclaimer.notice2.content",
    },
    {
      icon: Clock,
      titleKey: "disclaimer.notice3.title",
      contentKey: "disclaimer.notice3.content",
    },
    {
      icon: FileText,
      titleKey: "disclaimer.notice4.title",
      contentKey: "disclaimer.notice4.content",
    },
  ];

  const userResponsibilities = [
    "disclaimer.responsibilities.list1",
    "disclaimer.responsibilities.list2",
    "disclaimer.responsibilities.list3",
    "disclaimer.responsibilities.list4",
    "disclaimer.responsibilities.list5",
    "disclaimer.responsibilities.list6",
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
              <AlertTriangle className="w-10 h-10 text-primary-foreground" />
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-5xl lg:text-6xl leading-tight mb-6">
              {t("disclaimer.page.title")}
            </h1>
            <p className="text-lg sm:text-xl text-muted-foreground leading-relaxed">
              {t("disclaimer.page.subtitle")}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Key Notices */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="font-display text-2xl sm:text-3xl font-bold text-center mb-12"
          >
            {t("disclaimer.keyNotices")}
          </motion.h2>

          {importantNotices.map((notice, i) => (
            <motion.div
              key={notice.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="mb-6"
            >
              <GlassCard className="p-6 sm:p-8 border-l-4 border-l-yellow-500">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center flex-shrink-0">
                    <notice.icon className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h2 className="font-display text-xl font-semibold mb-3">
                      {t(notice.titleKey)}
                    </h2>
                    <p className="text-muted-foreground leading-relaxed">
                      {t(notice.contentKey)}
                    </p>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      </section>

      {/* User Responsibilities */}
      <section className="py-16 px-4 bg-card/30">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-6 sm:p-8">
              <h2 className="font-display text-xl font-semibold mb-6">
                {t("disclaimer.responsibilities.title")}
              </h2>
              <p className="text-muted-foreground mb-6">
                {t("disclaimer.responsibilities.subtitle")}
              </p>
              <ul className="space-y-4">
                {userResponsibilities.map((responsibilityKey, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                    <span className="text-muted-foreground">
                      {t(responsibilityKey)}
                    </span>
                  </li>
                ))}
              </ul>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* Scheme Information */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-6 sm:p-8">
              <h2 className="font-display text-xl font-semibold mb-4">
                {t("disclaimer.schemes.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                {t("disclaimer.schemes.content")}
              </p>
              <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-2">
                <li>{t("disclaimer.schemes.list1")}</li>
                <li>{t("disclaimer.schemes.list2")}</li>
                <li>{t("disclaimer.schemes.list3")}</li>
                <li>{t("disclaimer.schemes.list4")}</li>
              </ul>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* Limitation of Liability */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-6 sm:p-8">
              <h2 className="font-display text-xl font-semibold mb-4">
                {t("disclaimer.liability.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                {t("disclaimer.liability.content")}
              </p>
              <ul className="list-disc list-inside text-muted-foreground space-y-2 ml-2">
                <li>{t("disclaimer.liability.list1")}</li>
                <li>{t("disclaimer.liability.list2")}</li>
                <li>{t("disclaimer.liability.list3")}</li>
                <li>{t("disclaimer.liability.list4")}</li>
              </ul>
              <p className="text-muted-foreground leading-relaxed mt-4">
                {t("disclaimer.liability.content2")}
              </p>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* Agreement */}
      <section className="py-16 px-4">
        <div className="container mx-auto text-center max-w-2xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <GlassCard className="p-8">
              <h2 className="font-display text-xl font-semibold mb-4">
                {t("disclaimer.agreement.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                {t("disclaimer.agreement.content")}
              </p>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Disclaimer;
