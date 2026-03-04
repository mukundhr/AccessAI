import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { 
  FileUp, Brain, MessageSquareText, Volume2, Landmark, 
  ShieldCheck, Languages, Zap, Heart, Users, Target, User
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import GlassCard from "@/components/GlassCard";

const About = () => {
  const team = [
    { name: "Arun Arya", role: "Team Leader & Tester", description: "Arun leads the team with clear vision and coordination. He also ensures the quality and performance of our project through thorough testing.", icon: User },
    { name: "Mukundh Reddy", role: "Core Designer & Backend Developer", description: "Mukundh is responsible for designing the core system architecture and implementing the backend functionality that powers our application.", icon: User },
    { name: "Chandan Hegde", role: "Frontend Developer & Designer", description: "Chandan handles the frontend implementation and design, creating an intuitive and engaging user experience.", icon: User },
  ];

  const stats = [
    { value: "50K+", label: "Reports Analyzed" },
    { value: "12+", label: "Languages Supported" },
    { value: "98%", label: "User Satisfaction" },
    { value: "24/7", label: "Availability" },
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
            <h1 className="font-display font-bold text-3xl sm:text-5xl lg:text-6xl leading-tight mb-6">
              About <span className="gradient-text">Us</span>
            </h1>
            <h2 className="text-xl sm:text-2xl font-semibold mb-4">Welcome to AccessAI</h2>
            <p className="text-lg sm:text-xl text-muted-foreground leading-relaxed">
              We are a passionate team working together to build innovative AI-powered solutions 
              that can make a positive impact. Our goal is to leverage AWS technologies and 
              artificial intelligence to create smart, scalable, and user-friendly applications.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-16 px-4">
        <div className="container mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              <div className="w-16 h-16 rounded-2xl gradient-bg flex items-center justify-center mb-6">
                <Target className="w-8 h-8 text-primary-foreground" />
              </div>
              <h2 className="font-display text-2xl sm:text-3xl font-bold mb-4">Our Mission</h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                AccessAI was born from a simple observation: millions of people struggle to understand 
                their medical reports every day. Complex medical jargon, language barriers, and limited 
                access to healthcare professionals create significant challenges.
              </p>
              <p className="text-muted-foreground leading-relaxed">
                We believe that everyone deserves to understand their health information. Our AI-powered 
                platform simplifies medical reports into plain language, provides audio explanations in 
                local languages, and helps users discover government healthcare schemes they're eligible for.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="grid grid-cols-2 gap-4"
            >
              {stats.map((stat, i) => (
                <GlassCard key={stat.label} delay={i * 0.1} className="text-center p-4">
                  <div className="font-display text-3xl font-bold gradient-text mb-1">{stat.value}</div>
                  <div className="text-sm text-muted-foreground">{stat.label}</div>
                </GlassCard>
              ))}
            </motion.div>
          </div>
        </div>
      </section>

      {/* Features We Offer */}
      <section className="py-16 px-4">
        <div className="container mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="font-display text-2xl sm:text-3xl font-bold text-center mb-12"
          >
            What We <span className="gradient-text">Offer</span>
          </motion.h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <FileUp className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">Multi-Format Upload</h3>
              <p className="text-sm text-muted-foreground">
                Upload PDFs, images (JPG, PNG), or photos of your medical reports. Our OCR technology 
                extracts text accurately from various document types.
              </p>
            </GlassCard>

            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <Brain className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">AI-Powered Analysis</h3>
              <p className="text-sm text-muted-foreground">
                Our advanced AI analyzes your reports and provides easy-to-understand explanations 
                with confidence levels, so you know how certain the AI is about its analysis.
              </p>
            </GlassCard>

            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <MessageSquareText className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">Doctor Questions</h3>
              <p className="text-sm text-muted-foreground">
                Get generated questions to ask your doctor during appointments. Be prepared 
                and make the most of your consultation time.
              </p>
            </GlassCard>

            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <Volume2 className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">Audio Output</h3>
              <p className="text-sm text-muted-foreground">
                Listen to explanations in Hindi, Kannada, and other regional languages. 
                Our natural voice synthesis makes it feel like a real conversation.
              </p>
            </GlassCard>

            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <Landmark className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">Scheme Matching</h3>
              <p className="text-sm text-muted-foreground">
                Discover government healthcare schemes you're eligible for based on your 
                profile. We match you with relevant welfare programs.
              </p>
            </GlassCard>

            <GlassCard hover className="p-6">
              <div className="w-12 h-12 rounded-xl gradient-bg-subtle flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">Low Bandwidth</h3>
              <p className="text-sm text-muted-foreground">
                Designed to work on 2G/3G connections and low-end devices. AccessAI brings 
                healthcare accessibility to even the most remote areas.
              </p>
            </GlassCard>
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="py-16 px-4">
        <div className="container mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="font-display text-2xl sm:text-3xl font-bold text-center mb-4"
          >
            Our <span className="gradient-text">Team</span>
          </motion.h2>
          <p className="text-center text-muted-foreground mb-12 max-w-2xl mx-auto">
            Meet the passionate individuals behind AccessAI
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {team.map((member, i) => (
              <motion.div
                key={member.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <GlassCard className="text-center p-6 h-full">
                  <div className="w-14 h-14 rounded-full gradient-bg flex items-center justify-center mx-auto mb-4">
                    <member.icon className="w-7 h-7 text-primary-foreground" />
                  </div>
                  <h3 className="font-display font-semibold text-foreground">{member.name}</h3>
                  <p className="text-sm text-primary font-medium mb-3">{member.role}</p>
                  <p className="text-sm text-muted-foreground leading-relaxed">{member.description}</p>
                </GlassCard>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-4">
        <div className="container mx-auto text-center">
          <GlassCard className="max-w-2xl mx-auto p-8">
            <h2 className="font-display text-2xl font-bold mb-4">Ready to Get Started?</h2>
            <p className="text-muted-foreground mb-6">
              Upload your medical report now and get instant, easy-to-understand explanations.
            </p>
            <Link
              to="/upload"
              className="btn-primary-gradient inline-flex items-center gap-2 px-8 py-3 text-lg font-semibold"
            >
              Try It Now
            </Link>
          </GlassCard>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About;
