from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import tensorflow as tf
import numpy as np

import time
import discogan

import sys
sys.path.insert(0, '../')

import image_utils as iu
from datasets import Pix2PixDataSet as DataSets


dirs = {
    'sample_output': './DiscoGAN/',
    'checkpoint': './model/checkpoint',
    'model': './model/DiscoGAN-model.ckpt'
}
paras = {
    'epoch': 200,
    'batch_size': 64,
    'logging_interval': 5
}


def main():
    start_time = time.time()  # clocking start

    # Dataset
    dataset = DataSets(input_height=64,
                       input_width=64,
                       input_channel=3,
                       batch_size=paras['batch_size'],
                       name="vangogh2photo")

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    with tf.Session(config=config) as s:
        # DiscoGAN model
        model = discogan.DiscoGAN(s)

        # load model & graph & weight
        ckpt = tf.train.get_checkpoint_state('./model/')
        if ckpt and ckpt.model_checkpoint_path:
            # Restores from checkpoint
            model.saver.restore(s, ckpt.model_checkpoint_path)

            step = ckpt.model_checkpoint_path.split('/')[-1].split('-')[-1]
            print("[+] global step : %s" % step, " successfully loaded")
        else:
            step = 0
            print('[-] No checkpoint file found')

        # initializing variables
        tf.global_variables_initializer().run()

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(coord=coord)

        d_overpowered = False  # G loss > D loss * 2
        for epoch in range(paras['epoch']):
            for step in range(1000):
                offsetA = (step * paras['batch_size']) % (dataset.img_A.shape[0] - paras['batch_size'])
                offsetB = (step * paras['batch_size']) % (dataset.img_B.shape[0] - paras['batch_size'])

                # batch data set
                batch_A = dataset.img_A[offsetA:(offsetA + paras['batch_size']), :]
                batch_B = dataset.img_B[offsetB:(offsetB + paras['batch_size']), :]

                # update D network
                if not d_overpowered:
                    s.run(model.d_op, feed_dict={model.A: batch_A})

                # update G network
                s.run(model.g_op, feed_dict={model.B: batch_B})

                if epoch % paras['logging_interval'] == 0:
                    d_loss, g_loss, summary = s.run([
                        model.d_loss,
                        model.g_loss,
                        model.merged
                    ], feed_dict={
                        model.A: batch_A,
                        model.B: batch_B
                    })

                    # print loss
                    print("[+] Epoch %03d Step %04d => " % (epoch, step),
                          "D loss : {:.8f}".format(d_loss), " G loss : {:.8f}".format(g_loss))

                    # update overpowered
                    d_overpowered = d_loss < g_loss / 2

                    # training G model with sample image and noise
                    AB_samples = s.run(model.G_s2b, feed_dict={model.A: batch_A})
                    BA_samples = s.run(model.G_b2s, feed_dict={model.B: batch_B})

                    # summary saver
                    model.writer.add_summary(summary, epoch)

                    # export image generated by model G
                    sample_image_height = model.sample_size
                    sample_image_width = model.sample_size
                    sample_AB_dir = dirs['sample_output'] + 'train_A_{0}_{1}.png'.format(epoch, step)
                    sample_BA_dir = dirs['sample_output'] + 'train_B_{0}_{1}.png'.format(epoch, step)

                    # Generated image save
                    iu.save_images(AB_samples, size=[sample_image_height, sample_image_width],
                                   image_path=sample_AB_dir)
                    iu.save_images(BA_samples, size=[sample_image_height, sample_image_width],
                                   image_path=sample_BA_dir)

                    # model save
                    model.saver.save(s, dirs['model'], global_step=step)

        end_time = time.time() - start_time

        # elapsed time
        print("[+] Elapsed time {:.8f}s".format(end_time))

        # close tf.Session
        s.close()

        coord.request_stop()
        coord.join(threads)

if __name__ == '__main__':
    main()
